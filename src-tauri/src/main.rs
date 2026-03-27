#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Condvar, Mutex},
    thread,
    time::{Duration, Instant},
};

use tauri::{Manager, RunEvent};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

struct BackendState {
    inner: Mutex<BackendInner>,
    ready: Condvar,
}

#[derive(Default)]
struct BackendInner {
    url: Option<String>,
    child: Option<Child>,
}

impl Default for BackendState {
    fn default() -> Self {
        Self {
            inner: Mutex::new(BackendInner::default()),
            ready: Condvar::new(),
        }
    }
}

fn pick_free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

fn check_health(port: u16) -> bool {
    let mut stream = match TcpStream::connect(("127.0.0.1", port)) {
        Ok(stream) => stream,
        Err(_) => return false,
    };

    let _ = stream.write_all(
        b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
    );

    let mut buffer = [0u8; 512];
    let read = match stream.read(&mut buffer) {
        Ok(read) => read,
        Err(_) => return false,
    };

    let response = String::from_utf8_lossy(&buffer[..read]);
    response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200")
}

fn wait_for_health(port: u16, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if check_health(port) {
            return true;
        }
        thread::sleep(Duration::from_millis(120));
    }
    false
}

fn bundled_backend_path(resource_dir: &Path) -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        resource_dir.join("anomalize-api.exe")
    }

    #[cfg(not(target_os = "windows"))]
    {
        resource_dir.join("anomalize-api")
    }
}

fn spawn_backend_sidecar(app: &tauri::AppHandle) -> Result<(String, Child), String> {
    let port = pick_free_port().map_err(|e| format!("failed to choose a port: {e}"))?;
    let base_url = format!("http://127.0.0.1:{port}");

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|_| "failed to resolve resource dir".to_string())?;
    let sidecar = bundled_backend_path(&resource_dir);

    let configure = |command: &mut Command| {
        command
            .env("ANOMALIZE_HOST", "127.0.0.1")
            .env("ANOMALIZE_PORT", port.to_string())
            .env("ANOMALIZE_LOG_LEVEL", "warning")
            .env(
                "ANOMALIZE_CORS_ORIGINS",
                "tauri://localhost,https://tauri.localhost,http://tauri.localhost,http://localhost:5173",
            )
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        #[cfg(target_os = "windows")]
        {
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            command.creation_flags(CREATE_NO_WINDOW);
        }
    };

    let try_spawn_python = || -> Result<Child, String> {
        if !cfg!(debug_assertions) {
            return Err("bundled backend sidecar is missing or failed to start".to_string());
        }

        let src_python_dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../src-python");

        for python in ["python3", "python"] {
            let mut cmd = Command::new(python);
            cmd.arg("-m")
                .arg("uvicorn")
                .arg("main:app")
                .arg("--host")
                .arg("127.0.0.1")
                .arg("--port")
                .arg(port.to_string())
                .arg("--app-dir")
                .arg(&src_python_dir);
            configure(&mut cmd);
            if let Ok(child) = cmd.spawn() {
                return Ok(child);
            }
        }

        Err("failed to spawn backend via python (python3/python not found?)".to_string())
    };

    let mut child = if sidecar.exists() {
        let mut cmd = Command::new(&sidecar);
        configure(&mut cmd);
        match cmd.spawn() {
            Ok(child) => child,
            Err(_) => try_spawn_python()?,
        }
    } else {
        try_spawn_python()?
    };

    if !wait_for_health(port, Duration::from_secs(12)) {
        let _ = child.kill();

        // If the bundled sidecar was present but unhealthy, try the dev python fallback.
        if cfg!(debug_assertions) && sidecar.exists() {
            let mut python_child = try_spawn_python()?;
            if wait_for_health(port, Duration::from_secs(12)) {
                return Ok((base_url, python_child));
            }
            let _ = python_child.kill();
        }

        return Err("backend did not become healthy in time".to_string());
    }

    Ok((base_url, child))
}

#[tauri::command]
fn backend_base_url(state: tauri::State<BackendState>) -> Result<String, String> {
    let guard = state
        .inner
        .lock()
        .map_err(|_| "backend state poisoned".to_string())?;
    let (guard, _) = state
        .ready
        .wait_timeout_while(guard, Duration::from_secs(12), |inner| inner.url.is_none())
        .map_err(|_| "backend state poisoned".to_string())?;

    guard
        .url
        .clone()
        .ok_or_else(|| "backend not ready".to_string())
}

fn main() {
    let app = tauri::Builder::default()
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![backend_base_url])
        .setup(|app| {
            let handle = app.handle().clone();
            thread::spawn(move || {
                let result = spawn_backend_sidecar(&handle);
                let state: tauri::State<BackendState> = handle.state();

                match result {
                    Ok((url, child)) => {
                        let mut inner = state.inner.lock().expect("backend state poisoned");
                        inner.url = Some(url);
                        inner.child = Some(child);
                        state.ready.notify_all();
                    }
                    Err(error) => {
                        eprintln!("backend sidecar startup failed: {error}");
                        state.ready.notify_all();
                    }
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|handle, event| match event {
        RunEvent::ExitRequested { .. } | RunEvent::Exit => {
            let state: tauri::State<BackendState> = handle.state();
            let lock_result = state.inner.lock();
            if let Ok(mut inner) = lock_result {
                if let Some(mut child) = inner.child.take() {
                    let _ = child.kill();
                }
            }
        }
        _ => {}
    });
}
