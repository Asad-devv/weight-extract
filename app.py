import os
import json
import string
import streamlit as st
from datetime import datetime
from tempfile import mkdtemp
from PIL import Image
from pdf2image import convert_from_bytes
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
import google.generativeai as genai
from io import BytesIO

# 🔑 Gemini API Key (Secure way for Streamlit sharing)
genai.configure(api_key="AIzaSyD3T59ddtKIWiGRun31oCbdzba3ibm-He4")  # Or use st.text_input for local testing

# ✅ Clean output
def clean_text(text):
    text = ILLEGAL_CHARACTERS_RE.sub("", text)
    return ''.join(c for c in text if c in string.printable or c.isspace())

# ✅ Extract workout data from image using Gemini
def detect_workout_data(image_path):
    uploaded_file = genai.upload_file(image_path)
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = """
    The task is to extract workout data from the provided image or PDF. The goal is to detect and organize the following information:

    1. General Instructions:
      - The image is in complete handwritten form, so try to guess with higher accuracy.
      - Try to detect some texts that spill outside the WT and REPS columns.
      - Avoid unnecessary personal notes or decorative text.

    2. Data to Extract:
      - **Date** of the workout (if written on the page).
      - **Muscle group** targeted in the workout (e.g., Arms, Legs, Chest).
      - **Exercises** listed on the page.

    3. Sets and Reps:
      - For each exercise, extract the corresponding number of sets and reps.
      - Each set includes `weight (WT)` and `reps (REPS)`.
      - Each exercise usually contains **4 or 5 sets**, so expect at least that many.

    4. Output Format:
    Return the extracted data in this exact JSON format:

    {
      "date": "MM/DD/YYYY",
      "muscle_group": "Arms",
      "workouts": [
        {
          "exercise_name": "Exercise 1",
          "sets": [
            {"set_number": 1, "weight": "50kg", "reps": 10},
            {"set_number": 2, "weight": "55kg", "reps": 8},
            {"set_number": 3, "weight": "60kg", "reps": 6},
            {"set_number": 4, "weight": "65kg", "reps": 5},
            {"set_number": 5, "weight": "70kg", "reps": 4}
          ]
        },
        {
          "exercise_name": "Exercise 2",
          "sets": [
            {"set_number": 1, "weight": "40kg", "reps": 12},
            {"set_number": 2, "weight": "45kg", "reps": 10}
          ]
        }
      ]
    }

    Please return the result strictly in JSON and extract all relevant information from the image.
    """
    try:
        result = model.generate_content([uploaded_file, prompt])
        text = result.text
        start, end = text.find('{'), text.rfind('}') + 1
        json_str = text[start:end]
        return json.loads(json_str)
    except Exception as e:
        st.error(f"❌ Parsing error: {e}")
        return {'workouts': []}

# ✅ Excel Writer
def write_to_excel(data, file_index):
    wb = Workbook()
    ws = wb.active
    ws.append(["Date", "Muscle Group", "Exercise", "Set", "Weight", "Reps"])
    
    # Safely extract date and muscle_group from the data
    workout_date = data.get("date", datetime.now().strftime('%m/%d/%Y'))
    muscle_group = data.get("muscle_group", "Unknown")
    
    for workout in data.get('workouts', []):
        for s in workout.get('sets', []):
            ws.append([
                workout_date,
                muscle_group,
                workout.get('exercise_name', 'Unknown'),
                s.get('set_number', ''),
                s.get('weight', ''),
                s.get('reps', '')
            ])
    

    path = f"workout_{file_index}.xlsx"
    wb.save(path)
    return path
    print(f"✅ Downloaded workout_{file_index}.xlsx")


# ✅ Streamlit UI
st.title("🏋️ Workout Data Extractor")
st.markdown("Upload a scanned PDF or an image of a handwritten workout log to extract structured data.")

file_type = st.radio("Select file type:", ["PDF", "Image (JPG/PNG)"])

uploaded_files = st.file_uploader("Upload your file(s)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True)

if st.button("📤 Process"):
    if not uploaded_files:
        st.warning("Please upload at least one file.")
    else:
        image_paths = []

        # Process PDF or images
        for file in uploaded_files:
            if file_type == "PDF":
                images = convert_from_bytes(file.read())
                for i, img in enumerate(images):
                    path = os.path.join(mkdtemp(), f"page_{i+1}.png")
                    img.save(path, "PNG")
                    image_paths.append(path)
            else:
                img = Image.open(file)
                path = os.path.join(mkdtemp(), file.name)
                img.save(path)
                image_paths.append(path)

        # Process each image
        for idx, img_path in enumerate(image_paths):
            st.write(f"🔍 Processing: {os.path.basename(img_path)}")
            data = detect_workout_data(img_path)
            excel_path = write_to_excel(data, idx + 1)
            with open(excel_path, "rb") as f:
                st.download_button(
                    label=f"📥 Download workout_{idx+1}.xlsx",
                    data=f,
                    file_name=f"workout_{idx+1}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
