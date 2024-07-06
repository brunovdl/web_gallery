from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import sqlite3
from werkzeug.utils import secure_filename
import os
from functools import wraps
from PIL import Image
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['WATERMARK'] = 'static/images/logoieq.png'

# Configuração do banco de dados
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def add_watermark(input_image_path, watermark_image_path, output_image_path, transparency=128):
    base_image = Image.open(input_image_path).convert("RGBA")
    watermark = Image.open(watermark_image_path).convert("RGBA")

    # Redimensiona a marca d'água
    width, height = base_image.size
    watermark = watermark.resize((int(width / 6), int(height / 8)), Image.Resampling.LANCZOS)

    # Ajusta a transparência da marca d'água
    transparent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    transparent.paste(base_image, (0, 0))
    transparent.paste(watermark, (width - watermark.size[0] - 10, height - watermark.size[1] - 10), mask=watermark)

    # Salva a imagem com transparência em PNG
    transparent.save(output_image_path, format='PNG')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Você precisa estar logado para acessar esta página.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    conn = get_db_connection()
    fotos = conn.execute('SELECT * FROM fotos').fetchall()
    conn.close()
    return render_template('index.html', fotos=fotos)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'files' not in request.files:
            flash('Nenhuma parte do arquivo.')
            return redirect(request.url)
        files = request.files.getlist('files')
        if not files:
            flash('Nenhum arquivo selecionado!')
            return redirect(request.url)
        conn = get_db_connection()
        username = conn.execute('SELECT username FROM users WHERE id = ?', (session['user_id'],)).fetchone()['username']
        last_photo_id = conn.execute('SELECT MAX(id) FROM fotos').fetchone()[0] or 0

        for index, file in enumerate(files, start=1):
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Inclui a data no nome do arquivo
                date_str = datetime.now().strftime("%d-%m-%Y_%H:%M")
                watermarked_filename = f'{index}_{username}_{date_str}.png'
                watermarked_path = os.path.join(app.config['UPLOAD_FOLDER'], watermarked_filename)
                
                add_watermark(file_path, app.config['WATERMARK'], watermarked_path)

                conn.execute('INSERT INTO fotos (filename) VALUES (?)', (watermarked_filename,))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/delete/<int:photo_id>', methods=['POST'])
@login_required
def delete_photo(photo_id):
    conn = get_db_connection()
    foto = conn.execute('SELECT * FROM fotos WHERE id = ?', (photo_id,)).fetchone()
    if foto is None:
        flash('Foto não encontrada.')
        return redirect(url_for('index'))
    conn.execute('DELETE FROM fotos WHERE id = ?', (photo_id,))
    conn.commit()
    conn.close()

    # Remover a foto do sistema de arquivos
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], foto['filename']))
    flash(f'Foto {photo_id} apagada com sucesso.')
    return redirect(url_for('index'))

@app.route('/download/<filename>', methods=['GET'])
def download_photo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user:
            if user['password'] == password:
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash(f'Bem Vindo {username}!')
                return redirect(url_for('index'))
            else:
                flash('Senha Incorreta. Tente novamente.')
        else:
            flash('Usuário não enconrado. Por favor faça registro.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash(f'Logout efetuado com sucesso!')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user_exists = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user_exists:
            flash('Nome de usuário existente. Por favor escolha um nome diferente.')
        else:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            flash('Registro efetuado com sucesso. Faça login.')
            return redirect(url_for('index'))
        conn.close()
    return render_template('register.html')

if __name__ == '__main__':
    app.run(debug=True)
