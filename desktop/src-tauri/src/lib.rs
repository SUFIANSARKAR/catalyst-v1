use serde_json::{json, Value};
use std::process::Command;

fn run_command(program: &str, args: &[&str]) -> Result<String, String> {
    let output = Command::new(program).args(args).output().map_err(|e| e.to_string())?;
    if output.status.success() { Ok(String::from_utf8_lossy(&output.stdout).trim().to_string()) }
    else { Err(String::from_utf8_lossy(&output.stderr).trim().to_string()) }
}

#[tauri::command]
fn desktop_execute(action: String, payload: Value) -> Result<Value, String> {
    match action.as_str() {
        "get_system_info" => Ok(json!({
            "ok":true,
            "platform": std::env::consts::OS,
            "arch": std::env::consts::ARCH,
        })),
        "open_url" | "open_file" => {
            let target = payload.get(if action == "open_url" {"url"} else {"path"}).and_then(|v| v.as_str()).ok_or("missing target")?;
            #[cfg(target_os = "windows")]
            { run_command("cmd", &["/C", "start", "", target])?; }
            #[cfg(target_os = "macos")]
            { run_command("open", &[target])?; }
            #[cfg(all(unix, not(target_os = "macos")))]
            { run_command("xdg-open", &[target])?; }
            Ok(json!({"ok":true,"target":target}))
        }
        "show_notification" => {
            let title = payload.get("title").and_then(|v|v.as_str()).unwrap_or("Catalyst");
            let body = payload.get("body").and_then(|v|v.as_str()).unwrap_or("Catalyst notification");
            #[cfg(target_os = "linux")]
            { run_command("notify-send", &[title, body])?; }
            #[cfg(target_os = "macos")]
            { let script = format!("display notification {:?} with title {:?}", body, title); run_command("osascript", &["-e", &script])?; }
            #[cfg(target_os = "windows")]
            { let script = format!("[console]::beep(900,180); Write-Host '{}: {}'", title.replace('\'',""), body.replace('\'',"")); run_command("powershell", &["-NoProfile","-Command",&script])?; }
            Ok(json!({"ok":true,"shown":true}))
        }
        _ => Err(format!("Unsupported desktop action: {}", action)),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![desktop_execute])
        .run(tauri::generate_context!())
        .expect("error while running Catalyst Desktop");
}
