import plistlib

from itaca_idoceo.integrations import _write_macos_quick_action


def test_macos_quick_action_is_valid_plist(tmp_path):
    workflow = tmp_path / "Abrir en ITACA a iDoceo.workflow"
    _write_macos_quick_action(workflow)

    with (workflow / "Contents" / "document.wflow").open("rb") as fh:
        document = plistlib.load(fh)
    with (workflow / "Contents" / "Info.plist").open("rb") as fh:
        info = plistlib.load(fh)

    assert document["workflowMetaData"]["workflowTypeIdentifier"] == "com.apple.Automator.servicesMenu"
    assert document["workflowMetaData"]["serviceInputTypeIdentifier"] == "com.apple.Automator.fileSystemObject"
    command = document["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
    assert "itaca_idoceo.gui" in command
    assert '"$@"' in command
    assert info["NSServices"][0]["NSMessage"] == "runWorkflowAsService"
