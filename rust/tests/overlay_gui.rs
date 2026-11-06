//! Observe the Combat overlay on a private X output, including cross-language rectangle parity.
#![cfg(feature = "test-source")]

mod common;

#[test]
fn overlay_on_owned_display() {
    let output = std::process::Command::new(common::python())
        .args(["-B", "-m", "unittest", "test_overlay_gui.OverlayGui.test_rust_window", "-v"])
        .current_dir(common::repo().join("tests"))
        .env("DEHULUD_OVERLAY_BIN", common::combat_bin())
        .output()
        .expect("overlay probe runner");
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}
