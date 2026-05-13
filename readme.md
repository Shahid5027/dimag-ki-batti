# 🎓 AMCEC Campus Digital Ecosystem

> **Team Dimag Ki Batti** · Department of ECE · AMC Engineering College

A full-stack campus management platform built with **Flask + SQLite**, featuring AI-powered study tools, QR-based attendance, academic notes sharing, timetable management, and a student query board.

---

## 📋 Table of Contents

- [Features Overview](#-features-overview)
- [Modules](#-modules)
  - [Authentication & Security](#-authentication--security)
  - [Study AI (Concept Chef)](#-study-ai-concept-chef)
  - [Attendance System](#-attendance-system)
  - [Notes Hub](#-notes-hub)
  - [Timetable](#-timetable)
  - [Query Board](#-query-board)
  - [Admin Panel](#-admin-panel)
- [Tech Stack](#-tech-stack)
- [Local Setup](#-local-setup)
- [Environment Variables](#-environment-variables)
- [Default Credentials](#-default-credentials)
- [Project Structure](#-project-structure)
- [Hosting Recommendation](#-hosting-recommendation)

---

## ✨ Features Overview

| Feature | Description |
|---|---|
| 🤖 **Study AI** | AI-generated quizzes, mind maps, X-Ray notes, and detailed notes from YouTube / PDF / Text |
| 📸 **QR Attendance** | Faculty generates rotating QR codes; students scan to mark presence |
| 🔒 **Device Binding** | Students are permanently locked to their login device — prevents attendance fraud |
| 📂 **Notes Hub** | Hierarchical PDF notes library organized by Department → Subject |
| 📅 **Timetable** | Faculty & admin manage class schedules |
| 💬 **Query Board** | Students raise questions; faculty respond |
| 🛡️ **Role-Based Access** | Separate dashboards and permissions for Admin, Faculty, and Student |
| 📊 **Attendance Analytics** | Per-session attendance with date, time, and running percentage |

---

## 📦 Modules

### 🔐 Authentication & Security

- **Three roles**: `admin`, `faculty`, `student`
- **Permanent sessions** (30-day login persistence)
- **Device Binding (Anti-Fraud)**:
  - On first login, a student's browser is permanently tied to their USN via a 1-year `device_id` cookie stored in the database
  - Attempting to log in as a **different student from the same device is blocked**
  - Students **cannot log out** — the nav shows a 🔒 Locked badge
  - **Admin can unbind** a device from the Admin Panel to allow re-login from a new device
- Faculty and Admin can log out normally

**Login credentials format:**
| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Faculty | `teacher` | `teacher123` |
| Student | `143` (suffix only) | Set by admin or `student123` |

---

### 🤖 Study AI (Concept Chef)

Accessible at `/study/` — an AI-powered learning assistant using **Google Gemini**.

#### Input Sources
| Tab | Description |
|---|---|
| **YouTube** | Paste a YouTube URL — transcript is auto-fetched and processed |
| **PDF** | Upload a PDF — text is extracted and analyzed |
| **Text** | Paste raw notes or paragraphs |
| **Gemini** | Paste a Gemini chat log for concept extraction |

#### Study Modes
| Mode | What it does |
|---|---|
| **Standard Mix** | Summary bullets, analogy, embedded YouTube player, MCQ + cloze quiz |
| **X-Ray Mode** | 4-layer progressive reveal: Skeleton → Structure → Logic → Mastery |
| **Detailed Notes** | Structured exam-ready notes; PDF sources show an embedded viewer; YouTube/Text use AI generation |

#### Additional Features
- 🗺️ **Mind Map** — Mermaid.js auto-generated concept graph
- ⭐ **Quiz Arena** — MCQ and fill-in-the-blank questions with instant feedback
- 💬 **AI Chat Widget** — floating chat with Tutor or Examiner mode (uses session context)
- 🎤 **Voice Input** — speak your question via Web Speech API

---

### 📸 Attendance System

#### For Faculty / Admin
- Generates a **rotating QR code** that expires every 5 seconds and auto-regenerates
- QR encodes a one-time token URL — cannot be reused after expiry
- View a full **attendance register matrix** (students × sessions)
- **Download CSV** of the complete attendance register
- Apply for **Regular Leave** (≥12 hrs in advance) or **Emergency Leave** (≥1 hr in advance)

#### For Students
- Scan the QR code with their phone to mark **Present** for the current class hour
- View personal attendance record with:
  - **Session name** (1st Hour, 2nd Hour, etc.)
  - **Date** and **Time** of marking
  - **Running attendance %** per row (color-coded: 🟢 ≥75% · 🟡 ≥50% · 🔴 <75%)
  - **Overall percentage ring chart** (warns if below 75%)
- Duplicate marking for the same session is blocked

#### Class Schedule (IST)
| Period | Time |
|---|---|
| 1st Hour | 09:15 – 10:10 |
| 2nd Hour | 10:10 – 11:05 |
| Short Break | 11:05 – 11:20 |
| 3rd Hour | 11:20 – 12:15 |
| 4th Hour | 12:15 – 13:10 |
| Lunch Break | 13:10 – 14:00 |
| 5th Hour | 14:00 – 14:55 |
| 6th Hour | 14:55 – 15:50 |
| 7th Hour | 15:50 – 16:45 |

---

### 📂 Notes Hub

- Faculty / Admin can upload PDF notes with:
  - **Title**, **Subject**, **Department**, **Sub-Department**
- Notes are organized in a **hierarchical tree**: `Department → Subject → Notes`
- Any logged-in user can **view** (inline PDF) or **download** notes
- Faculty / Admin can **delete** notes they uploaded

---

### 📅 Timetable

- Faculty and Admin can create and manage class timetables
- Students can view their department's timetable
- Supports per-day, per-period slot management

---

### 💬 Query Board

- Students post academic questions
- Faculty can reply publicly
- Supports upvoting and resolution marking
- All roles can browse the board at `/queries/`

---

### 🛡️ Admin Panel

Located at `/attendance/admin` — Admin-only controls:

| Section | Actions |
|---|---|
| **Student Registration** | Register a new student USN + password |
| **Device Bindings** | View all bound devices; unbind any student with one click |
| **Faculty Leave Requests** | Approve or reject leave applications |
| **Attendance Logs** | Live log of all attendance entries with USN, session, and timestamp |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, Flask |
| **Database** | SQLite (via `sqlite3`) |
| **AI** | Google Gemini (`google-genai` SDK) |
| **Frontend** | Vanilla HTML / CSS / JavaScript |
| **PDF Parsing** | PyPDF2 |
| **QR Codes** | `qrcode` + Pillow |
| **YouTube Transcripts** | `youtube-transcript-api` |
| **Mind Maps** | Mermaid.js (CDN) |

---

## ⚙️ Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/Shahid5027/dimag-ki-batti.git
cd dimag-ki-batti
```

### 2. Create a virtual environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Run the app
```bash
python main.py
```

Open **http://localhost:5000** in your browser.

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key — get one at [aistudio.google.com](https://aistudio.google.com) |
| `VERCEL` | Auto | Set to `1` automatically on Vercel — switches DB/upload paths to `/tmp` |

---

## 👤 Default Credentials

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Faculty | `teacher` | `teacher123` |
| Faculty (email) | `teacher@amcec.edu` | `teacher123` |
| Student | `143` *(or full USN)* | `student123` *(or admin-set)* |

> ⚠️ **Change the admin password and `app.secret_key` in `main.py` before deploying to production.**

---

## 📁 Project Structure

```
dimag-ki-batti/
├── main.py                  # Flask app, notes routes
├── config.py                # Gemini API config
├── requirements.txt
├── vercel.json              # Vercel deployment config
├── .env                     # Environment variables (not committed)
│
├── routes/
│   ├── auth_api.py          # Login, logout, device binding
│   ├── attendance_api.py    # QR generation, attendance marking, admin
│   ├── study_api.py         # AI study generation, notes, chat
│   ├── queries_api.py       # Query board
│   └── timetable_api.py     # Timetable management
│
├── templates/
│   ├── _partials/           # Reusable nav, head HTML
│   ├── dashboard.html
│   ├── login.html
│   ├── study.html
│   ├── attendance_student.html
│   ├── attendance_faculty.html
│   ├── attendance_admin.html
│   ├── attendance_qr.html
│   ├── notes.html
│   ├── timetable.html
│   └── queries.html
│
├── static/
│   ├── css/                 # Global design system
│   └── js/                  # Animations, utilities
│
├── database/                # SQLite DB files (auto-created)
│   ├── attendance.db
│   └── notes.db
│
└── uploads/                 # Uploaded PDF files (auto-created)
```

---

## 🚀 Hosting Recommendation

| Platform | Verdict | Notes |
|---|---|---|
| **Render** ⭐ | Best fit | Persistent disk, native Flask, free tier available |
| **Railway** | Great | Persistent disk, ~$5/mo |
| **PythonAnywhere** | Good | Free tier, easy for Python projects |
| **Vercel** | ⚠️ Limited | SQLite resets between requests — data loss risk |
| **Heroku** | ❌ Avoid | Ephemeral filesystem, SQLite not supported |

**Recommended: [Render.com](https://render.com)**
- Set **Start Command**: `python main.py`
- Add env var: `GEMINI_API_KEY=your_key`
- SQLite persists on disk — no data loss

---

## 👥 Team

**Team Dimag Ki Batti**  
Department of Electronics & Communication Engineering  
AMC Engineering College, Bengaluru

---

## 📄 License

This project is built for educational purposes at AMCEC. All rights reserved © 2026 Team Dimag Ki Batti.
