import time
from openpyxl import Workbook
from flask import send_file
import io
import csv
from flask import Response
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request

app = Flask(__name__)

URL = "https://sbtet.ap.gov.in/APSBTET/gradeWiseResults.do"


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/fetch', methods=['POST'])
def fetch_results():
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

    all_results = []

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

        # -------- student info ----------
        for row in rows:
            ths = row.find_all("th")
            tds = row.find_all("td")
            if len(ths) == 1 and len(tds) == 1:
                student[ths[0].text.strip()] = tds[0].text.strip()

        # -------- subject info ----------
        for row in rows:
            ths = row.find_all("th")
            tds = row.find_all("td")
            if len(ths) == 1 and len(tds) >= 7:
                code = ths[0].text.strip()
                if code == "Paper":
                    continue
                subjects.append({
                    "code": code,
                    "status": tds[6].text.strip()
                })

        # -------- fail count ----------
        fail_count = 0
        for sub in subjects:
            if sub["status"] == "F":
                fail_count += 1

        name = student.get("Name", "")

        if name == "":
            all_results.append({
                "roll": roll_no,
                "name": "—",
                "total": "—",
                "result": "NO RESULT",
                "fail_count": None
            })
        else:
            all_results.append({
                "roll": roll_no,
                "name": name,
                "total": student.get("Grand Total", ""),
                "result": student.get("Result", ""),
                "fail_count": fail_count
            })
            


    # -------- analysis ----------
    pass_all = fail_1 = fail_2 = fail_3 = fail_4_plus = 0

    for r in all_results:
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

    #to get stored bulk results and to use them to download in a file
    global LAST_BULK_RESULTS
    LAST_BULK_RESULTS = all_results
     
    
    return render_template(
        "bulk_results.html",
        results=all_results,
        pass_all=pass_all,
        fail_1=fail_1,
        fail_2=fail_2,
        fail_3=fail_3,
        fail_4_plus=fail_4_plus,
        semester=semester
    )


@app.route('/download_excel')
def download_excel():
    global LAST_BULK_RESULTS

    wb = Workbook()
    ws = wb.active
    ws.title = "Bulk Results"

    # Header row
    ws.append([
        "Roll No",
        "Name",
        "Grand Total",
        "Result",
        "Failed Subjects Count"
    ])

    # Data rows
    for r in LAST_BULK_RESULTS:
        ws.append([
            r["roll"],
            r["name"],
            r["total"],
            r["result"],
            "" if r["fail_count"] is None else r["fail_count"]
        ])

    # Save to memory (not disk)
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name="bulk_results.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



# -------- single student page --------
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

    # ---------------- PHOTO EXTRACTION ----------------
    photo_src = None
    img = soup.find("img", {"alt": "NO FILE"})
    if img and img.get("src", "").startswith("data:image"):
        photo_src = img["src"]
    # --------------------------------------------------

    # ---------------- STUDENT DETAILS -----------------
    student = {"PIN": roll_no}

    for row in rows:
        ths = row.find_all("th")
        tds = row.find_all("td")
        if len(ths) == 1 and len(tds) == 1:
            student[ths[0].text.strip()] = tds[0].text.strip()

    # ✅ THIS IS THE LINE YOU ASKED ABOUT
    student["photo"] = photo_src
    # --------------------------------------------------

    # ---------------- SUBJECT DETAILS -----------------
    subjects = []

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
    # --------------------------------------------------

    return render_template("result.html", data={
        "student": student,
        "subjects": subjects
    })



if __name__ == '__main__':
    app.run()
