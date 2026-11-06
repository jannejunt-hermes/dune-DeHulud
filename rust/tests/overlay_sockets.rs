//! Observe both production binaries on the owned display in a private PID namespace.
#![cfg(not(feature = "test-source"))]

mod common;

#[test]
fn production_windows_use_only_unix_sockets() {
    let output = std::process::Command::new(common::python())
        .args(["-B", "-m", "unittest", "test_overlay_gui.OverlayGui.test_production_socket_snapshots", "-v"])
        .current_dir(common::repo().join("tests"))
        .env("DEHULUD_SOCKET_PLAIN_BIN", common::bin())
        .env("DEHULUD_SOCKET_COMBAT_BIN", common::combat_bin())
        .output()
        .expect("production socket probe runner");
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}
