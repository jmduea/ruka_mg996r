# RUKA MG996R - Webcam-Controlled Robotic Hand

The [RUKA robotic hand](https://ruka-hand.github.io/) adapted for use with MG996R servos and controllable via webcam hand-tracking or keyboard input.

## Overview

This project is an adaptation of the original [RUKA robotic hand](https://ruka-hand.github.io/) design, replacing the most expensive components in the design with inexpensive and widely available alternatives. I found the original RUKA hand design to be very interesting and something I wanted to try building myself and incorporate into other projects I'm working on, but the cost and availability of the required components made it impractical for me as an individual hobbyist/developer to pursue. Thus, I created this adaptation that tries to maintain the core functionality of the RUKA hand while using components that are more accessible, making it feasible for myself and others to build and experiment with an incredibly well-designed robotic hand before investing in the higher-end version if desired.

## How is this different?

This project differs from the original RUKA hand design in two main ways:

1. Cost and Accessibility of Components

   - The original RUKA hand design requires:

     - 3 [DYNAMIXEL XM430-W350-R](https://www.robotis.us/dynamixel-xm430-w350-r/) motors ($333.39 each as of 1/27/26)
     - 8 [DYNAMIXEL XL330-M288-T](https://www.robotis.us/dynamixel-xl330-m288-t/) motors ($27.49 each as of 1/27/26, ALSO on backorder)
     - [Manus Gloves](https://www.manus-meta.com/) which as far as I can tell require purchasing a license to use them, aren't easily available for individual purchase, and represent an unknown cost due to opacity around pricing.

   - These components add up to well over $1,200 USD, and are difficult to source from the perspective of an individual hobbyist/developer.

   - This adaptation uses these components to replace the above components:

     - 11 [MG996R servos](https://www.amazon.com/dp/B0BMM1G74B?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1) ($26.98 for a 6-pack as of 1/27/26)
     - A standard webcam for hand-tracking (many laptops have these built-in, or they can be purchased for relatively cheap)
   - These components were chosen for their low cost and wide availability, but do come with trade-offs in terms of the capabilities of the robotic hand.

2. Capabilities and Performance

   - The original RUKA hand design, with its high-end DYNAMIXEL motors and Manus Gloves, offers:

     - High precision in finger movements
     - Advanced hand-tracking capabilities with the Manus Gloves
     - Smooth and responsive control of the robotic hand
     - Closed-loop feedback for precise positioning

   - This adaptation, using MG996R servos and webcam-based hand-tracking, offers:

     - Adequate precision and torque for basic finger movements, but may lack the finesse of the original design
     - Hand-tracking capabilities that depend on the quality of the webcam and the effectiveness of the hand-tracking software used
     - Control that may be less smooth and responsive compared to the original setup
     - Open-loop control without feedback, which may lead to less accurate positioning

   - While this adaptation may not match the performance of the original RUKA hand, it provides a more accessible entry point for hobbyists and developers interested in robotic hands (the main reason for this adaptation).

### Architecture

```
┌─────────────────────────────┐         ┌─────────────────────────────┐
│      Windows PC (Client)    │         │    Raspberry Pi (Server)    │
│                             │         │                             │
│  ┌─────────┐  ┌───────────┐ │         │ ┌─────────┐  ┌───────────┐  │
│  │ Webcam  │──│ MediaPipe │ │WebSocket│ │ FastAPI │──│  Servo    │  │
│  │ Capture │  │ Tracking  │─┼────────►│ │ Server  │  │Controller │  │
│  └─────────┘  └───────────┘ │         │ └─────────┘  └─────┬─────┘  │
│                             │         │                    │        │
└─────────────────────────────┘         │              ┌─────▼─────┐  │
                                        │              │  PCA9685  │  │
                                        │              │  + MG996R │  │
                                        │              └───────────┘  │
                                        └─────────────────────────────┘
```

## Hardware Requirements

For building the robotic hand, you should refer to the original [RUKA Bill of Materials](https://ruka.gitbook.io/instructions/hardware/bill-of-materials) for 3D printed parts and other non-electronic components. Anything with the Part Type **Motor/Controls** or **Power Supply** can be ignored, but the rest is still applicable.

### Raspberry Pi (Server)

- [Raspberry Pi 3 B+ or newer](https://www.raspberrypi.com/products/raspberry-pi-3-model-b/)
- [PCA9685 16-channel PWM driver](https://www.adafruit.com/product/815)
- 11x [MG996R servos](https://www.amazon.com/dp/B0BMM1G74B?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1)
- 5V 20A power supply for servos
- wires, breadboard, and other electronics components as needed

### Windows PC (Client)

- Webcam (built-in or external)
  - I personally used a [Logitech C922](https://www.logitech.com/en-us/shop/p/c922-pro-stream-webcam), but any decent quality webcam should work.

## Software Requirements

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager (optional, but **HIGHLY** recommended)

## Installation

### Install uv (Both Systems)

[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Raspberry Pi (Linux):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone Repository (Both Systems)

```bash
git clone https://github.com/jmduea/ruka_mg996r.git
```

### Raspberry Pi Setup (Server)

1. **Enable I2C:**

    ```bash
    sudo raspi-config
    # Navigate to: Interface Options -> I2C -> Enable
    ```

2. **Install Dependencies:**

    ```bash
    sudo apt update
    sudo apt install -y python3-dev i2c-tools
    ```

3. **Verify I2C connection:**

    ```bash
    sudo i2cdetect -y 1
    # Should show device at address 0x40 (PCA9685)
    ```

4. **Install Python Packages:**

    ```bash
    cd ruka_mg996r
    uv sync --extra server --extra calibration
    ```

5. **Create calibration directory:**

    ```bash
    mkdir -p data/calibration
    ```

### PC Setup (Client)

1. **Install Python Packages:**

    ```powershell
    cd ruka_mg996r
    uv sync --extra client
    ```

## Calibration (Raspberry Pi)

**Important:** Run calibration steps in order!

### Step 1: Find Servo Ranges (BEFORE installing tendons)

- 500-2500 microseconds is the typical range for MG996R servos, but they *can* vary.
- While not strictly necessary, it's recommended to calibrate each servo to find its actual min/max range.

```bash
# On Raspberry Pi
uv run ruka-calibrate range
```

Follow the on-screen instructions to move each servo to its minimum and maximum positions.

The calibration data will be saved in `data/calibration/mg996r_calibration.json` by default.

### Step 2: Calibrate Tendons (AFTER installing tendons/complete hand assembly)

```bash
# On Raspberry Pi
uv run ruka-calibrate tendons
```

This finds the taut (tendon in tension with joint open) and curled (joint closed) positions for each finger.

It will update the calibration file located at `data/calibration/mg996r_calibration.json`.

### Step 3: Test Calibration (Optional, but recommended)

```bash
# On Raspberry Pi
uv run ruka-calibrate test
```

## Running the System

### 1. Start the Server (Raspberry Pi)

```bash
uv run ruka-server --host 0.0.0.0 --port 8000
```

Options:

- `--host`: Network interface to bind (default: 0.0.0.0)
- `--port`: Port to listen on (default: 8000)
- `--simulate`: Run without hardware for testing (default: False)
- `--calibration`: Path to calibration file (default: `data/calibration/mg996r_calibration.json`)

### 2. Start the Client (PC)

```powershell
uv run ruka-client --server ws://RASPBERRY_PI_IP:8000/ws/control
```

Replace `RASPBERRY_PI_IP` with the actual IP address of your Raspberry Pi (find it with `hostname -I` on the Pi).

Options:

- `--server`: WebSocket server URL
- `--camera`: Camera index (default: 0)
- `--hand`: Which hand to track (left/right, default: right)
- `--no-preview`: Disable webcam preview window

### Client Controls (WIP)

## Configuration (WIP)

## Project Structure

```
ruka_mg996r/
├── pyproject.toml          # Project configuration
├── README.md
├── src/
│   └── ruka/
│       ├── server/         # FastAPI server (runs on Pi)
│       ├── client/         # Hand tracking client (runs on PC)
│       ├── calibration/    # Calibration tools (runs on Pi)
│       └── shared/         # Shared code
├── data/
│   └── calibration/        # Calibration files
├── tests/                  # Test suite
└── scripts/                # Helper scripts
```

## Troubleshooting (WIP)

## Development (WIP)

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [RUKA Hand](https://ruka-hand.github.io/) - Original hand design and assembly instructions
- [MediaPipe](https://mediapipe.dev/) - Hand tracking
- [Adafruit](https://www.adafruit.com/) - ServoKit library and PCA9685 driver
