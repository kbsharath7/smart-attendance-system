# Attendance system and student emotion based engagement prediction

## Folder layout
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
```
## Run
```
pip install -r requirements.txt
python app.py          # http://127.0.0.1:5000
```
Admin login: `admin` / `admin123`. Faculty accounts are created by the admin.

## Notes
* Camera windows open on the computer that runs Flask. Press `c` to capture a face sample, `q` to finish.
* Face folders are named by USN, so `recognition.py` returns USNs directly.
* Slideshow: drop your own images into `static/slides/` and they replace the default stock photos.
* Change departments in `database.py` (`DEFAULT_DEPARTMENTS`), the admin password in `app.py`, and set `SECRET_KEY` in production.
* Engagement score: happy 100, surprise 90, neutral 70, fear 35, angry 30, disgust 20, sad 20 (edit `EMOTION_WEIGHTS` in `app.py`).
* If DeepFace complains about Keras on newer TensorFlow, `pip install tf-keras`.

## Roles and logins
| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Faculty | created by admin (subjects are picked from the built-in catalog) | set by admin |
| Student | the student's **name** (not case sensitive) | the student's **USN** |

## Marks, events, leave, reports
* Marks per subject: internal /50, activity /20, lab /30 (change in `database.py`: `INTERNAL_MAX, ACTIVITY_MAX, LAB_MAX`). Lab is only enabled for subjects flagged `has_lab` in the catalog.
* Subject catalog: `SUBJECT_CATALOG` in `database.py` (69 real-world subjects across the 7 departments). Add or edit entries there; new ones are inserted on the next start.
* Events: images are saved to `static/uploads/events/`.
* Leave requests go to faculty of the student's department, and to faculty who have taught that student's class. Approved leave is flagged on the attendance review screen.
* Excel: admin (Reports page, Attendance page, student page), faculty (Reports page, student rows, monitoring results) and students (their own report).
