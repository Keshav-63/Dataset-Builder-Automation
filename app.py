import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from dataset_builder import process_excel_dataset, identify_columns
from generate_sample_excel import create_sample_excel
from verify_dataset import inspect_mp4
import pandas as pd

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['DATASET_FOLDER'] = os.path.join(os.getcwd(), 'dataset_clips')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max upload

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DATASET_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sample_excel')
def download_sample():
    sample_path = os.path.join(app.config['UPLOAD_FOLDER'], 'cricket_clips_input.xlsx')
    create_sample_excel(sample_path)
    return send_file(sample_path, as_attachment=True, download_name='cricket_clips_template.xlsx')

@app.route('/api/inspect_file', methods=['POST'])
def inspect_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
            
        col_map = identify_columns(df)
        
        rows_sample = []
        for idx, row in df.head(5).iterrows():
            rows_sample.append({
                'row_id': idx + 1,
                'url': str(row.get(col_map.get('url'), '')),
                'start': str(row.get(col_map.get('start'), '')),
                'end': str(row.get(col_map.get('end'), '')),
                'subfolder': str(row.get(col_map.get('subfolder'), '')) if col_map.get('subfolder') else f"clip"
            })
            
        return jsonify({
            'filepath': filepath,
            'total_rows': len(df),
            'columns': list(df.columns),
            'detected_columns': col_map,
            'preview': rows_sample
        })
    except Exception as e:
        return jsonify({'error': f"Failed to parse spreadsheet: {str(e)}"}), 500

@app.route('/api/start_download', methods=['POST'])
def start_download():
    data = request.json
    filepath = data.get('filepath')
    workers = int(data.get('workers', 4))
    target_fps = int(data.get('target_fps', 60))
    max_res = int(data.get('max_res', 720))
    out_dir = data.get('output_folder', app.config['DATASET_FOLDER'])
    overwrite = bool(data.get('overwrite', False))
    
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Spreadsheet file not found on server'}), 400
        
    try:
        results = process_excel_dataset(filepath, output_dir=out_dir, max_workers=workers, target_fps=target_fps, max_res=max_res, overwrite=overwrite)
        return jsonify({
            'status': 'complete',
            'results': results,
            'output_dir': os.path.abspath(out_dir)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/list_clips')
def list_clips():
    out_dir = app.config['DATASET_FOLDER']
    if not os.path.exists(out_dir):
        return jsonify([])
        
    clips = []
    for root, _, files in os.walk(out_dir):
        for f in files:
            if f.endswith('.mp4'):
                full_p = os.path.join(root, f)
                info = inspect_mp4(full_p)
                info['rel_path'] = os.path.relpath(full_p, out_dir)
                clips.append(info)
    return jsonify(clips)

if __name__ == '__main__':
    print(f"\n🚀 Cricket Dataset Builder Web App starting on http://127.0.0.1:5000\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
