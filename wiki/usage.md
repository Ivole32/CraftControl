The EXE file comes with a preconfigured config for the `DDJ FLX-4` DJ controller for Minecraft. It can be used otherwise and can adapt to every other game/application. This guide uses Minecraft as an example, and some features may work differently for other applications.

## Set up Minecraft
When using Minecraft, you have to change some settings. These are **optional** but recommended for a good experience.

1. If you plan to control the mouse with the controller, go to `Options > Controls > Mouse Settings` and turn "Raw Input" off. You may need to change the "Sensitivity" value here later.

2. The default configuration does not allow holding a sneak or sprint button, so it is recommended to set Sneak and Sprint to Toggle in `Options > Controls`.

## Configure keyboard/mouse bindings
First, you need to start the application and select your MIDI device (DJ controller, ...). If no device is shown, make sure your device is connected and click the "Refresh" button. After that, you can start by clicking the "Start" button. If you click a button or move a fader on the controller, you should see some output in the "MIDI Monitor Output" tab. Now you can use the preconfigured config or make your own.

### MIDI Output structure explained
To properly understand how to configure mouse/keyboard bindings, you need to understand the output shown in "MIDI Monitor Output".

The first value in every log line is the message type. For the `DDJ FLX-4`, there are usually only "control_change" for faders and "note_on" for buttons in use.

The next value, `channel`, is the message channel the message is sent to.

The next value, `control` or `note`, contains the ID of the specific button or fader (faders usually use two, but more on that later).

Next is `value` or `velocity`, which both stand for the value the MIDI controller is transmitting (e.g. 127 if a button is pressed and 0 if it is released).

You can safely ignore `time`.

### Keyboard Bindings
To add keyboard bindings, you have to press the button on your MIDI controller you want to select and look in the log which message values it has. Then you need to paste those into the keyboard tab, add an action key, and press "Add". If you want to use the jog wheels for WASD, you have to specify the value. But for other keybinds, you may not need that.

Please note that you can use shortcuts. You can read the documentation for that [here](https://github.com/boppreh/keyboard#keyboardsendhotkey-do_presstrue-do_releasetrue) (The documentation is a bit confusing but you'll understand it.)

### Mouse Bindings

#### **Movement**
**Warning:** Movement is only supported for faders and knobs.

Move the fader or knob and look out for two messages in the log. You need to do everything as described for the keyboard and leave the value empty, as the code has to read it itself. Key 1 and key 2 are the control values of both messages.

#### **Clicking**
**Warning:** Clicking is only supported for buttons.

Do everything as described for mouse bindings, but make key 1 and key 2 the same value. Also make sure that you configure a click and release action for right and left click. You can do that with the optional values. The "mouse_click_middle" action has no release action, as it releases itself.