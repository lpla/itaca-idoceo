import plistlib

from itaca_idoceo.integrations import _write_macos_quick_action


def test_macos_quick_action_is_valid_plist(tmp_path):
    workflow = tmp_path / "Abrir en ITACA a iDoceo.workflow"
    _write_macos_quick_action(workflow)

    with (workflow / "Contents" / "document.wflow").open("rb") as fh:
        document = plistlib.load(fh)
    with (workflow / "Contents" / "Info.plist").open("rb") as fh:
        info = plistlib.load(fh)

    metadata = document["workflowMetaData"]
    assert metadata["workflowTypeIdentifier"] == "com.apple.Automator.servicesMenu"
    assert metadata["serviceInputTypeIdentifier"] == "com.apple.Automator.fileSystemObject"
    assert metadata["applicationBundleIDsByPath"]["/System/Library/CoreServices/Finder.app"] == "com.apple.finder"
    assert metadata["applicationPaths"] == ["/System/Library/CoreServices/Finder.app"]
    assert metadata["systemImageName"] == "NSActionTemplate"
    assert metadata["presentationMode"] == 15

    action = document["actions"][0]["action"]
    assert action["AMAccepts"]["Types"] == ["com.apple.cocoa.string"]
    command = action["ActionParameters"]["COMMAND_STRING"]
    assert "itaca_idoceo.gui" in command
    assert '"$@"' in command

    service = info["NSServices"][0]
    assert service["NSMessage"] == "runWorkflowAsService"
    assert service["NSRequiredContext"]["NSApplicationIdentifier"] == "com.apple.finder"
    assert service["NSSendFileTypes"] == ["public.item"]
    assert service["NSIconName"] == "NSActionTemplate"
