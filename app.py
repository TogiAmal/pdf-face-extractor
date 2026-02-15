import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import zipfile
import os

# --- APP CONFIGURATION ---
st.set_page_config(page_title="PDF Face Extractor", layout="centered")
st.title("📂 PDF Face & Photo Extractor")
st.write("Upload a directory PDF to extract faces in exact reading order (Left -> Right).")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Settings")
    min_width = st.slider("Min Width (px)", 50, 500, 100)
    min_height = st.slider("Min Height (px)", 50, 500, 100)
    row_tolerance = st.slider("Row Alignment (px)", 0, 50, 10)
    st.info("Adjust these if you are missing photos or getting too many logos.")

# --- PROCESSING FUNCTION ---
def extract_images_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    extracted_images = []
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    total_pages = len(doc)

    global_count = 0

    for page_index, page in enumerate(doc):
        # Update progress
        progress_bar.progress((page_index + 1) / total_pages)
        status_text.text(f"Scanning Page {page_index + 1} of {total_pages}...")

        image_list = page.get_images(full=True)
        images_on_page = []

        # 1. Gather Images & Positions
        for img in image_list:
            xref = img[0]
            rects = page.get_image_rects(xref)
            if rects:
                y = rects[0].y0
                x = rects[0].x0
                images_on_page.append({'y': y, 'x': x, 'xref': xref})

        # 2. Sort (Vertical first)
        images_on_page.sort(key=lambda k: k['y'])

        # 3. Group into Rows (The "Reading Order" Logic)
        sorted_final = []
        if images_on_page:
            current_row = [images_on_page[0]]
            for i in range(1, len(images_on_page)):
                img = images_on_page[i]
                prev_img = current_row[-1]
                
                # Check alignment (Row Detection)
                if abs(img['y'] - prev_img['y']) < row_tolerance:
                    current_row.append(img)
                else:
                    current_row.sort(key=lambda k: k['x']) # Sort row Left-to-Right
                    sorted_final.extend(current_row)
                    current_row = [img]
            current_row.sort(key=lambda k: k['x'])
            sorted_final.extend(current_row)

        # 4. Extract & Convert
        for img_data in sorted_final:
            xref = img_data['xref']
            try:
                pix = fitz.Pixmap(doc, xref)
                
                # Convert CMYK/Grayscale to RGB if needed
                if pix.n - pix.alpha < 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                
                # Check Size
                if pix.width >= min_width and pix.height >= min_height:
                    global_count += 1
                    
                    # Convert to PNG bytes
                    img_bytes = pix.tobytes("png")
                    filename = f"img_{global_count:03d}_page{page_index+1}.png"
                    extracted_images.append((filename, img_bytes))
                    
                pix = None
            except Exception as e:
                print(f"Error: {e}")

    return extracted_images

# --- USER INTERFACE ---
uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    if st.button("Start Extraction"):
        with st.spinner("Processing... This might take a minute for large files."):
            images = extract_images_from_pdf(uploaded_file)
            
            if images:
                st.success(f"Success! Extracted {len(images)} images.")
                
                # Create ZIP in memory
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for filename, img_bytes in images:
                        zf.writestr(filename, img_bytes)
                
                # Download Button
                st.download_button(
                    label="Download All Images (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="extracted_faces.zip",
                    mime="application/zip"
                )
            else:
                st.warning("No images found! Try lowering the 'Min Width' in the sidebar.")