# IoT Based Smart Classroom Occupancy with Energy Monitoring

A smart classroom project that combines a **face-recognition attendance and engagement web application** with an **ESP32-based classroom hardware model**.

The software marks attendance automatically, detects fake faces, estimates student engagement from facial emotions, and gives admins, faculty and students their own dashboards. The hardware senses who is in the room, switches lights and cooling only when they are needed, detects fire, shows live readings on an LCD, and sends alerts to Telegram.

---

## Table of Contents

1. [Features](#features)
2. [System Overview](#system-overview)
3. [Components Used](#components-used)
4. [Software & Libraries](#software--libraries)
5. [How the Software Works](#how-the-software-works)
6. [How the Hardware Works](#how-the-hardware-works)
7. [Configured Thresholds](#configured-thresholds)
8. [Project Images](#project-images)
9. [Installation and Setup](#installation-and-setup)
10. [Project Code](#project-code)
11. [Folder Layout](#folder-layout)
12. [Roles and Logins](#roles-and-logins)
13. [Notes](#notes)
14. [Future Improvements](#future-improvements)
15. [Author](#author)

---

## Features

### Software
- Face-recognition attendance using MTCNN face detection and FaceNet embeddings
- Liveness detection to reject photos and screens shown to the camera
- Class monitoring with emotion detection to estimate student engagement
- Three role-based dashboards: admin, faculty and student
- Attendance shortage tracking, with students below 75% flagged automatically
- Manual attendance overrides with a recorded reason
- Marks entry per subject (internal, activity and lab)
- Study material upload, leave requests and event announcements
- Excel reports for the whole class and for individual students

### Hardware
- Occupancy sensing with left and right IR sensors
- Automatic light control using an LDR (darkness) sensor
- Automatic cooling relay when the room is warm and occupied
- Fire detection with a flame sensor, a relay response and a Telegram alert
- Temperature and humidity monitoring with a DHT11 sensor
- 16x2 LCD showing live readings and room status
- Motor movement driven automatically by the IR sensors, plus manual control over serial
- Appliances run only when someone is present, which avoids wasting energy

---

## System Overview

```
                 SOFTWARE                                    HARDWARE

Camera --> Face detection (MTCNN)                 IR sensors (left / right) --+
              |                                   LDR light sensor -----------+
              v                                   Flame sensor ---------------+--> ESP32 --> Relays --> Lights / Cooling / Fire response
       Face recognition (FaceNet)                 DHT11 temperature + humidity +      |
              |                                                                       +--> 16x2 LCD
              v                                                                       +--> Motor driver --> DC motor
       Liveness check                                                                 +--> WiFi --> Telegram alerts
              |
              v
   Flask web app + SQLite database
              |
              v
   Admin / Faculty / Student dashboards
   + Excel reports
```

---

## Components Used

### Software
| Area | Tools |
|---|---|
| Backend | Python, Flask |
| Database | SQLite |
| Face detection | OpenCV, MTCNN (`det1.npy`, `det2.npy`, `det3.npy`) |
| Face recognition | FaceNet (pretrained model `20170512-110547`) |
| Emotion detection | DeepFace |
| Reports | openpyxl (Excel .xlsx) |
| Frontend | HTML, CSS, JavaScript with Jinja templates |

### Hardware
| Component | Purpose |
|---|---|
| ESP32 DevKit (NodeMCU-ESP32) | Main controller with built-in WiFi |
| IR sensor modules (left and right) | Detect people entering and moving in the room |
| LDR light sensor module | Detects whether the room is dark |
| Flame sensor module | Detects fire |
| DHT11 sensor | Measures temperature and humidity |
| 4-channel relay module | Switches the fire response, cooling and two lights |
| 16x2 LCD | Displays temperature, humidity and status |
| DC motor with motor driver | Automatic movement driven by the IR sensors |
| Fan and mini water pump | Cooling and fire response |
| Battery and power supply | Powers the board and loads |

---

## Software & Libraries

**Attendance application**
- Python 3 and the packages listed in `requirements.txt`
- Flask, OpenCV, FaceNet (TensorFlow), DeepFace, openpyxl

**ESP32 firmware**
- Arduino IDE with the ESP32 Board Package
- DHT sensor library
- UniversalTelegramBot
- ArduinoJson
- LiquidCrystal and WiFi (included with the IDE and the ESP32 package)

---

## How the Software Works

### 1. Student enrolment
The admin adds a student with their name, USN and department. The student's face samples are captured through the camera (`dataset.py`) and stored in a folder named after the USN. Naming folders by USN means the recognition step returns USNs directly.

### 2. Taking attendance
1. Faculty open **Take attendance** and select the class and subject.
2. The camera opens on the computer running the app (`recognition.py`).
3. **MTCNN** detects each face and aligns it (`detect_and_align.py`).
4. **FaceNet** converts the face into an embedding and matches it against the enrolled students.
5. The **liveness check** (`liveness.py`) rejects printed photos and screens.
6. The recognised students are listed in an attendance review screen where faculty can confirm or correct the result before saving.

### 3. Manual overrides and leave
Faculty can change a student's attendance and must record a reason. Students can submit leave requests, which go to the faculty of their department and to the faculty who have taught their class. Approved leave is flagged on the attendance review screen.

### 4. Class monitoring and engagement
During a monitoring session (`monitor.py`) the camera recognises students and a worker process (`emotion_worker.py`, using DeepFace) detects their emotions. Each emotion is turned into an engagement score:

| Emotion | Score |
|---|---|
| Happy | 100 |
| Surprise | 90 |
| Neutral | 70 |
| Fear | 35 |
| Angry | 30 |
| Disgust | 20 |
| Sad | 20 |

The scores can be changed in `EMOTION_WEIGHTS` in `app.py`. Results are saved and shown on the monitoring result page.

### 5. Marks, materials and events
- **Marks** per subject: internal out of 50, activity out of 20, and lab out of 30. The lab mark is enabled only for subjects marked as having a lab.
- **Study material:** faculty upload files, and students of that class can download them.
- **Events:** faculty post event announcements with images, which students see on their dashboard.

### 6. Dashboards
| Role | What they can do |
|---|---|
| Admin | Overview, add and manage students and faculty, view attendance for every student, overrides, reports |
| Faculty | My subjects, take attendance, class monitoring, marks, study material, leave requests, events, reports |
| Student | Personal dashboard, attendance, study material, leave requests, events, own Excel report |

### 7. Reports
Excel reports are available to admin (class report, student report), faculty (class report, student rows, monitoring results) and students (their own report).

---

## How the Hardware Works

The ESP32 reads its sensors in a continuous loop and acts on the readings.

### Sensor inputs
| Sensor | Used for |
|---|---|
| Left IR and right IR | Detect a person on either side and drive the motor |
| LDR | Check if the room is dark |
| Flame sensor | Detect fire |
| DHT11 | Read temperature and humidity |

### Automatic behaviour
| Condition | Action |
|---|---|
| Flame detected | LCD shows `FIRE DETECTED`, Relay 1 turns on, a Telegram alert is sent |
| Temperature above 30 °C and someone detected | LCD shows `TEMP IS HIGH`, Relay 2 turns on for cooling |
| Temperature normal | LCD shows `TEMP NORMAL`, Relay 2 stays off |
| Dark room and left IR triggered | Relay 3 turns on the left light |
| Dark room and right IR triggered | Relay 4 turns on the right light |
| No one detected | Lights stay off |
| Left or right IR triggered | The motor moves forward or backward automatically |
| DHT11 read fails | LCD shows `DHT SENSOR ERROR` |

### Relay assignment
| Relay | ESP32 pin | Function |
|---|---|---|
| Relay 1 | 19 | Fire response |
| Relay 2 | 21 | Cooling when hot and occupied |
| Relay 3 | 22 | Left light |
| Relay 4 | 23 | Right light |

### Pin mapping
| Function | ESP32 pin |
|---|---|
| LCD RS, EN, D4, D5, D6, D7 | 13, 12, 14, 27, 26, 25 |
| Left IR, Right IR | 15, 2 |
| LDR | 4 |
| Flame sensor | 18 |
| DHT11 | 5 |
| Relays 1 to 4 | 19, 21, 22, 23 |
| Motor driver IN1, IN2 | 33, 32 |

### Manual control
Send these characters over the serial monitor at **9600 baud**:
- `F` forward
- `B` backward
- `S` stop

### Telegram alerts
The ESP32 connects to WiFi and sends a start-up message and fire alerts to a Telegram bot. You create the bot with **@BotFather** and find your chat ID with **@userinfobot**.

---

## Configured Thresholds

| Parameter | Value |
|---|---|
| Cooling relay turns on | Temperature above 30 °C with someone present |
| Attendance shortage | Below 75% |
| Attendance bands on the dashboard | Below 60%, 60 to 74%, 75% and above |
| Marks | Internal 50, activity 20, lab 30 |

---

## Project Images

### Faculty Dashboard
![Faculty Dashboard](images/faculty_dashboard.png)

### Admin Overview
![Admin Overview](images/admin_overview.png)

### Hardware Setup
![Hardware Setup](images/hardware_setup.jpeg)

### Sensors and Controller Close-up
![Sensors and Controller Close-up](images/sensors_closeup.jpeg)

---

## Installation and Setup

### A. Attendance software (Windows)

1. **Install Python 3** and check that `python` works in PowerShell.
2. **Clone the repository**
   ```
   git clone https://github.com/kbsharath7/smart-attendance-system.git
   cd smart-attendance-system
   ```
3. **Add the FaceNet model.** It is not included in this repository because of its size. Download the pretrained model `20170512-110547` from the [facenet repository](https://github.com/davidsandberg/facenet) and place the folder in the project root as `20170512-110547/`.
4. **First-time setup:** run `Setup_First_Time.bat`. It creates a virtual environment and installs the requirements.
5. **Start the app:** run `Start_Attendance_App.bat`, or run:
   ```
   pip install -r requirements.txt
   python app.py
   ```
6. Open **http://127.0.0.1:5000** in your browser.
7. Log in as admin, add faculty accounts, then enrol students and start taking attendance.

### B. ESP32 hardware

1. Install the **Arduino IDE** and add ESP32 board support through the Boards Manager.
2. Install the libraries: **DHT sensor library**, **UniversalTelegramBot**, **ArduinoJson**.
3. Wire the sensors, relays, LCD and motor driver as shown in the pin mapping table.
4. Open `hardware/esp32_classroom_occupancy/esp32_classroom_occupancy.ino`.
5. Replace the placeholders with your own details:
   ```cpp
   const char* ssid = "YOUR_WIFI_NAME";
   const char* password = "YOUR_WIFI_PASSWORD";
   #define BOT_TOKEN "YOUR_TELEGRAM_BOT_TOKEN"
   #define CHAT_ID "YOUR_TELEGRAM_CHAT_ID"
   ```
6. Select **ESP32 Dev Module** and the correct COM port, then click **Upload**.
7. Open the Serial Monitor at 9600 baud to see the sensor readings.

> **Security note:** never commit your real WiFi password or Telegram bot token to GitHub. Keep the placeholder version in the repository and edit credentials only on the copy you upload to the board.

---

## Project Code

| File | Purpose |
|---|---|
| `app.py` | Flask application and all routes |
| `database.py` | SQLite database layer (`attendance.db` is created on first run) |
| `reports.py` | Excel report builders |
| `face_common.py` | Shared FaceNet code (IdData, load_model, setup) |
| `dataset.py` | Face enrolment: `python dataset.py <USN>` |
| `detect_and_align.py` | MTCNN face detection and alignment |
| `recognition.py` | Attendance camera: `python recognition.py --out r.json` |
| `liveness.py` | Liveness check |
| `monitor.py` | Recognition plus emotion camera |
| `emotion_worker.py` | DeepFace worker used by `monitor.py` |
| `hardware/esp32_classroom_occupancy/esp32_classroom_occupancy.ino` | ESP32 firmware |

---

## Folder Layout
```
attendance_app/
├─ app.py              Flask app (routes)
├─ database.py         sqlite3 layer (attendance.db is created on first run)
├─ reports.py          Excel report builders (openpyxl)
├─ face_common.py      IdData / load_model / setup  (shared FaceNet code)
├─ dataset.py          face enrolment   (python dataset.py <USN>)
├─ recognition.py      attendance camera (python recognition.py --out r.json)
├─ monitor.py          recognition + emotion camera
├─ emotion_worker.py   DeepFace worker used by monitor.py
├─ detect_and_align.py <-- YOUR existing file, copy it here
├─ 20170512-110547/    <-- YOUR existing model folder (20170512-110547.pb), copy it here
├─ templates/  static/  tmp/
├─ hardware/           ESP32 firmware
└─ images/             project screenshots and photos
```

---

## Roles and Logins

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Faculty | created by admin (subjects are picked from the built-in catalog) | set by admin |
| Student | the student's **name** (not case sensitive) | the student's **USN** |

These are demo credentials for a college project. Change the admin password in `app.py` and set a `SECRET_KEY` environment variable before any real use.

---

## Notes
* Camera windows open on the computer that runs Flask. Press `c` to capture a face sample, `q` to finish.
* Face folders are named by USN, so `recognition.py` returns USNs directly.
* Slideshow: drop your own images into `static/slides/` and they replace the default stock photos.
* Change departments in `database.py` (`DEFAULT_DEPARTMENTS`), the admin password in `app.py`, and set `SECRET_KEY` in production.
* Engagement score: edit `EMOTION_WEIGHTS` in `app.py`.
* If DeepFace complains about Keras on newer TensorFlow, run `pip install tf-keras`.
* Marks maximums can be changed in `database.py` (`INTERNAL_MAX, ACTIVITY_MAX, LAB_MAX`).
* Subject catalog: `SUBJECT_CATALOG` in `database.py` (69 subjects across 7 departments). New entries are inserted on the next start.
* Events: images are saved to `static/uploads/events/`.
* Student face images, the database file, uploads and the FaceNet model are intentionally excluded from this repository to protect student privacy (see `.gitignore`).

---

## Future Improvements
- Show live hardware readings (temperature, occupancy, relay status) on the web dashboard
- Add measured energy usage with a current sensor
- Add mobile application support
- Strengthen the liveness detection
- Deploy the application on a cloud server

---

## Author

**K B Sharath**

GitHub: <https://github.com/kbsharath7>
