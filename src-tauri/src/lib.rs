use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("brasfoot-server")
                .expect("failed to create sidecar command");

            let (mut rx, child) = sidecar
                .spawn()
                .expect("failed to spawn sidecar");

            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                // Keep child handle alive so sidecar isn't killed on drop
                let _child = child;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let line_str = String::from_utf8_lossy(&line);
                            let trimmed = line_str.trim();
                            if let Some(port) = trimmed.strip_prefix("BRASFOOT_PORT=") {
                                let url = format!("http://127.0.0.1:{}", port);
                                eprintln!("[ultrafoot] sidecar ready on port {}", port);
                                if let Some(window) = app_handle.get_webview_window("main") {
                                    let _ = window.eval(&format!(
                                        "window.__BRASFOOT_API_URL='{}';",
                                        url
                                    ));
                                }
                            }
                        }
                        CommandEvent::Stderr(line) => {
                            let msg = String::from_utf8_lossy(&line);
                            if !msg.trim().is_empty() {
                                eprintln!("[sidecar] {}", msg.trim());
                            }
                        }
                        CommandEvent::Error(err) => {
                            eprintln!("[ultrafoot] sidecar error: {}", err);
                        }
                        CommandEvent::Terminated(payload) => {
                            eprintln!("[ultrafoot] sidecar terminated: {:?}", payload);
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
