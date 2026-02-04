import time
import io
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, send_file
from openpyxl import Workbook

app = Flask(__name__)

URL = "https://sbtet.ap.gov.in/APSBTET/gradeWiseResults.do"

# Global storage for downloads
LAST_BULK_RESULTS = []
LAST_EXCEL_DATA = []


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/fetch', methods=['POST'])
def fetch_results():
    global LAST_BULK_RESULTS, LAST_EXCEL_DATA

    LAST_BULK_RESULTS = []
    LAST_EXCEL_DATA = []

    circular_no = request.form['circular_no']
    college_code = request.form['college_code']
    branch_code = request.form['branch_code']
    semester = request.form['semester']
    roll_from = int(request.form['roll_from'])
    roll_to = int(request.form['roll_to'])

    roll_numbers = []
    for i in range(roll_from, roll_to + 1):
        roll_serial = str(i).zfill(3)
        roll_numbers.append(f"{circular_no}{college_code}-{branch_code}-{roll_serial}")

    for roll_no in roll_numbers:
        payload = {
            "aadhar1": roll_no,
            "grade2": semester,
            "mode": "getData"
        }

        response = requests.post(URL, data=payload)
        time.sleep(0.5)

        soup = BeautifulSoup(response.content, "html.parser")
        rows = soup.find_all("tr")

        student = {"PIN": roll_no}
        subjects = []

        # -------- Student details --------
        for row in rows:
            ths = row.find_all("th")
            tds = row.find_all("td")
            if len(ths) == 1 and len(tds) == 1:
                student[ths[0].text.strip()] = tds[0].text.strip()

        # -------- Subject details --------
        for row in rows:
            ths = row.find_all("th")
            tds = row.find_all("td")
            if len(ths) == 1 and len(tds) >= 7:
                code = ths[0].text.strip()
                if code == "Paper":
                    continue
                subjects.append({
                    "code": code,
                    "external": tds[0].text.strip(),
                    "internal": tds[1].text.strip(),
                    "total": tds[2].text.strip(),
                    "grade": tds[5].text.strip(),
                    "status": tds[6].text.strip()
                })

        # -------- Fail count --------
        fail_count = sum(1 for s in subjects if s["status"] == "F")
        name = student.get("Name", "")

        if name == "":
            LAST_BULK_RESULTS.append({
                "roll": roll_no,
                "name": "—",
                "total": "—",
                "result": "NO RESULT",
                "fail_count": None
            })
        else:
            LAST_BULK_RESULTS.append({
                "roll": roll_no,
                "name": name,
                "total": student.get("Grand Total", ""),
                "result": student.get("Result", ""),
                "fail_count": fail_count
            })

            # -------- Store FULL subject-wise data for Excel --------
            for sub in subjects:
                LAST_EXCEL_DATA.append({
                    "roll": roll_no,
                    "subject": sub["code"],
                    "external": sub["external"],
                    "internal": sub["internal"],
                    "total": sub["total"],
                    "grade": sub["grade"],
                    "status": sub["status"]
                })

            # Blank row between students
            LAST_EXCEL_DATA.append({
                "roll": "",
                "subject": "",
                "external": "",
                "internal": "",
                "total": "",
                "grade": "",
                "status": ""
            })

    # -------- Analysis --------
    pass_all = fail_1 = fail_2 = fail_3 = fail_4_plus = 0

    for r in LAST_BULK_RESULTS:
        fc = r["fail_count"]
        if fc is None:
            continue
        elif fc == 0:
            pass_all += 1
        elif fc == 1:
            fail_1 += 1
        elif fc == 2:
            fail_2 += 1
        elif fc == 3:
            fail_3 += 1
        else:
            fail_4_plus += 1

    return render_template(
        "bulk_results.html",
        results=LAST_BULK_RESULTS,
        pass_all=pass_all,
        fail_1=fail_1,
        fail_2=fail_2,
        fail_3=fail_3,
        fail_4_plus=fail_4_plus,
        semester=semester
    )


# -------- Download FULL Excel (subject-wise) --------
@app.route('/download_excel')
def download_excel():
    wb = Workbook()
    ws = wb.active
    ws.title = "Full Results"

    ws.append([
        "Roll No",
        "Subject Code",
        "External",
        "Internal",
        "Total",
        "Grade",
        "Status"
    ])

    for row in LAST_EXCEL_DATA:
        ws.append([
            row["roll"],
            row["subject"],
            row["external"],
            row["internal"],
            row["total"],
            row["grade"],
            row["status"]
        ])

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name="Full_Diploma_Results.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# -------- Single student view --------
@app.route('/student/<roll_no>/<semester>')
def view_student(roll_no, semester):
    payload = {
        "aadhar1": roll_no,
        "grade2": semester,
        "mode": "getData"
    }

    response = requests.post(URL, data=payload)
    soup = BeautifulSoup(response.content, "html.parser")
    rows = soup.find_all("tr")

    # Photo extraction (optional)
    photo_src = None
    img = soup.find("img", {"alt": "NO FILE"})
    if img and img.get("src", "").startswith("data:image"):
        photo_src = img["src"]

    student = {"PIN": roll_no, "photo": photo_src}
    subjects = []

    for row in rows:
        ths = row.find_all("th")
        tds = row.find_all("td")
        if len(ths) == 1 and len(tds) == 1:
            student[ths[0].text.strip()] = tds[0].text.strip()

    for row in rows:
        ths = row.find_all("th")
        tds = row.find_all("td")
        if len(ths) == 1 and len(tds) >= 7:
            code = ths[0].text.strip()
            if code == "Paper":
                continue
            subjects.append({
                "code": code,
                "external": tds[0].text.strip(),
                "internal": tds[1].text.strip(),
                "total": tds[2].text.strip(),
                "grade": tds[5].text.strip(),
                "status": tds[6].text.strip()
            })

    return render_template("result.html", data={
        "student": student,
        "subjects": subjects
    })


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)

  
