from flask import render_template, Response
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, session, send_file
import qrcode
import io
from io import BytesIO
import json
import os
import base64
import random
import string
from xhtml2pdf import pisa
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

app = Flask(__name__)

# Paths for the product storage file and upload folder
PRODUCTS_FILE = 'static/data/products.txt'
TYPES_FILE = 'static/data/product_types.json'
UPLOAD_FOLDER = 'static/uploads'
LAST_ID_FILE = 'static/data/last_id.txt'
CHAT_LOG_PATH = os.path.join('static', 'data', 'chat_log.json')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.urandom(24)  # Stronger secret key generation for security

messages = []

# Configuration       
cloudinary.config( 
    cloud_name = "dqaebcg0f", 
    api_key = "337718663574757", 
    api_secret = "Eqy-vTVqpzExiZrf55N7RYZy1R8", # Click 'View API Keys' above to copy your API secret
    secure=True
)

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Helper to load last used ID
def load_last_id():
    try:
        with open(LAST_ID_FILE, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        return '001'  # Start from 000 if file doesn't exist

# Helper to save last used ID
def save_last_id(last_id):
    with open(LAST_ID_FILE, 'w') as file:
        file.write(last_id)      

# Helper function to generate a QR code
def generate_qr(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    byte_io = BytesIO()
    img.save(byte_io, 'PNG')
    return base64.b64encode(byte_io.getvalue()).decode('utf-8')  # Return as base64 string

# Unique ID generator that ensures IDs are reused after deletion
def generate_unique_id():
    letters = string.ascii_uppercase
    last_id = load_last_id()
    
    if last_id.isnumeric():  # Handle numeric IDs 000 to 099
        number = int(last_id)
        if number < 99:
            new_id = str(number + 1).zfill(3)  # Increment and zero-fill to 3 digits
        else:
            new_id = "A01"  # Start letter sequence if numeric IDs are full
    else:  # Handle letter-based IDs e.g., A01, A02, ..., Z99
        letter, num_part = last_id[0], int(last_id[1:])
        if num_part < 99:
            new_id = f"{letter}{str(num_part + 1).zfill(2)}"
        else:
            next_letter = letters[(letters.index(letter) + 1) % len(letters)]
            new_id = f"{next_letter}01"  # Move to the next letter

    save_last_id(new_id)  # Update last_id.txt with the new ID
    return new_id

# Load and save functions for products and types
def load_products():
    try:
        with open(PRODUCTS_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def load_product_types():
    try:
        with open(TYPES_FILE, 'r') as file:
            content = file.read().strip()
            if content:
                return json.loads(content)
            else:
                return {}
    except FileNotFoundError:
        return {}

def save_products(products):
    with open(PRODUCTS_FILE, 'w') as file:
        json.dump(products, file, indent=4)

def save_product_types(types):
    with open(TYPES_FILE, 'w') as file:
        json.dump(types, file, indent=4)

# Helper functions for chat messages
def read_messages():
    if os.path.exists(CHAT_LOG_PATH):
        with open(CHAT_LOG_PATH, 'r') as f:
            return json.load(f)
    return []

def write_messages(messages):
    with open(CHAT_LOG_PATH, 'w') as f:
        json.dump(messages, f, indent=4)
        
@app.route('/photo')
def upload_page():
    return render_template('photo.html')
        
@app.route('/log')
def index():
    products = load_products()
    return render_template('index.html', products=products)

@app.route('/log/generate_qr/<string:product_id>', methods=['GET'])
def generate_qr_code(product_id):
    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    qr_code_data = f"{product_id}"
    qr_code_base64 = generate_qr(qr_code_data)

    return jsonify({'qr_code': qr_code_base64})

@app.route('/photo/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files')  # Get multiple files from the form
    uploaded_images = []

    for file in files:
        try:
            result = cloudinary.uploader.upload(file, public_id=file.filename)
            uploaded_images.append(result["secure_url"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"images": uploaded_images})

  
@app.route('/log/add_product', methods=['GET', 'POST'])
def add_product():
    product_types = load_product_types()
    if request.method == 'POST':
        product_type = request.form['product_type']
        name = request.form['name']
        quantity = request.form['quantity']
        p_name = request.form['p_name']
        hb = request.form['hb']
        condition = request.form['condition']
        date_r = request.form['date_r']

        settings = {'quantity': quantity}

        for param, value in request.form.items():
            if param not in ['product_type', 'name', 'quantity', 'p_name', 'hb', 'condition', 'date_r']:
                settings[param] = value

        products = load_products()
        product_id = generate_unique_id()

        product = {
            'id': product_id,
            'name': name,
            'type': product_type,
            'settings': settings,
            'p_name': p_name,
            'hb': hb,
            'condition': condition,
            'date_r': date_r,
            'image': None
        }

        products.append(product)
        save_products(products)

        return redirect(url_for('index'))

    return render_template('add_product.html', product_types=product_types)

@app.route('/search_by_id')
def search_by_id():
    query = request.args.get('query', '').strip()  # Get the query from the user input
    products = load_products()  # Load your products (from your file or database)

    # Find the product with the matching ID
    result = next((product for product in products if str(product['id']) == query), None)

    return render_template('search_results.html', query=query, result=result)


  
@app.route('/log/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    name = data.get('name')
    message = data.get('message')
    
    if name and message:
        messages = read_messages()
        messages.append({'name': name, 'message': message})
        write_messages(messages)
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid input'}), 400

@app.route('/log/get_messages')
def get_messages():
    messages = read_messages()
    return jsonify({'messages': messages})

@app.route('/log/chat')
def chat():
    return render_template('chat.html')

@app.route('/log/settings', methods=['GET', 'POST'])
def settings():
    product_types = load_product_types()
    if request.method == 'POST':
        if 'add_type' in request.form:
            new_type = request.form['new_type']
            if new_type and new_type not in product_types:
                product_types[new_type] = {}

        elif 'add_parameter' in request.form:
            selected_type = request.form['selected_type']
            param_name = request.form['param_name']
            param_type = request.form['param_type']
            if selected_type and param_name:
                product_types[selected_type][param_name] = param_type

        save_product_types(product_types)
        return redirect(url_for('settings'))

    return render_template('settings.html', product_types=product_types)

@app.route('/log/remove_product/<string:product_id>')
def remove_product(product_id):
    products = load_products()
    products = [product for product in products if product['id'] != product_id]
    save_products(products)
    return redirect(url_for('index'))

@app.route('/log/viewer')
def viewer():
    return render_template('viewer.html')

@app.route('/log/table')
def table():
    products = load_products()
    return render_template('log_table.html', products=products)

@app.route('/log/generate_pdf')
def generate_pdf():
    rendered_html = render_template('log_table.html')
    pdf_buffer = io.BytesIO()
    
    try:
        pisa_status = pisa.CreatePDF(rendered_html, dest=pdf_buffer)
        
        if pisa_status.err:
            return f"Error: {str(pisa_status.err)}", 500
        
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name='log_table.pdf',
            mimetype='application/pdf'
        )
    
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/log/view_product/<string:product_id>')
def view_product(product_id):
    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)
    return render_template('view_product.html', product=product)

@app.route('/log/edit_product/<string:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    products = load_products()
    product = next((p for p in products if p['id'] == product_id), None)
    if not product:
        return redirect(url_for('index'))

    if request.method == 'POST':
        product['name'] = request.form['name']
        product['type'] = request.form['product_type']
        product['settings'] = {'quantity': request.form['quantity']}
        
        save_products(products)
        return redirect(url_for('index'))
    
    product_types = load_product_types()
    return render_template('edit_product.html', product=product, product_types=product_types)

@app.route('/')
def starter():
  return render_template('starter.html')

# Run the application
if __name__ == '__main__':
    app.run(debug=True)
