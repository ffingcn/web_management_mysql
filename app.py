# -*- coding: utf-8 -*-
import os
import ssl
import json
import threading
import time
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from functools import wraps
import pymysql
from dbutils.pooled_db import PooledDB
from flask_caching import Cache
from flask_compress import Compress

current_dir = os.path.dirname(os.path.abspath(__file__))

LOG_DIR = os.path.join(current_dir, 'log')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'run.log')

HISTORY_DIR = os.path.join(current_dir, 'history')
os.makedirs(HISTORY_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(HISTORY_DIR, 'history.json')

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载历史记录失败: {e}")
            return []
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"保存历史记录失败: {e}")
        return False

def add_history_record(action_type, status, database, table, record_data=None, field_order=None):
    from datetime import datetime
    history = load_history()
    record = {
        'action_type': action_type,
        'status': status,
        'database': database,
        'table': table,
        'record_data': record_data,
        'field_order': field_order,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    history.insert(0, record)
    if len(history) > 500:
        history = history[:500]
    save_history(history)
    return record

file_handler = TimedRotatingFileHandler(
    LOG_FILE,
    when='D',
    interval=1,
    backupCount=7,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler(sys.stdout)
    ]
)

app = Flask(__name__, template_folder=os.path.join(current_dir, 'templates'))
app.secret_key = os.urandom(24)

# 缓存配置
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5分钟缓存
app.config['CACHE_THRESHOLD'] = 100  # 缓存最大条目数
cache = Cache(app)
Compress(app)

# 数据库连接池（延迟初始化）
db_pool = None

CONF_DIR = os.path.join(current_dir, 'conf')
CONFIG_FILE = os.path.join(CONF_DIR, 'config.json')

LOGIN_CONFIG = {}
DB_CONFIG_BASE = {}
SERVER_CONFIG = {}
SITE_CONFIG = {}
PAGE_CONFIG = {}

def load_config():
    global LOGIN_CONFIG, DB_CONFIG_BASE, SERVER_CONFIG, SITE_CONFIG, PAGE_CONFIG
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            LOGIN_CONFIG = {
                'username': config['login']['username'],
                'password': config['login']['password'],
                'max_attempts': 3,
                'lockout_duration': 300,
                'retry_window': 300
            }
            
            DB_CONFIG_BASE = {
                'host': config['database']['host'],
                'port': int(config['database']['port']) if config['database']['port'] else '',
                'user': config['database']['user'],
                'password': config['database']['password'],
                'charset': 'utf8mb4',
                'cursorclass': pymysql.cursors.DictCursor
            }
            
            SERVER_CONFIG = {
                'http_port': int(config['server']['http_port']) if config['server']['http_port'] else '',
                'https_port': int(config['server']['https_port']) if config['server']['https_port'] else '',
                'ssl_cert': config['server']['ssl_cert'],
                'ssl_key': config['server']['ssl_key']
            }
            
            SITE_CONFIG = {
                'name': config.get('site', {}).get('name', ''),
                'logo': config.get('site', {}).get('logo', '')
            }
            
            PAGE_CONFIG = {
                'default_database': config.get('page', {}).get('default_database', ''),
                'default_table': config.get('page', {}).get('default_table', ''),
                'default_page_size': config.get('page', {}).get('default_page_size', 10)
            }
            logging.info("配置加载成功")
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
            logging.error("请检查配置文件格式是否正确")
            sys.exit(1)
    else:
        logging.info(f"配置文件不存在: {CONFIG_FILE}，正在创建默认配置...")
        
        LOGIN_CONFIG = {
            'username': 'admin',
            'password': '123456',
            'max_attempts': 3,
            'lockout_duration': 300,
            'retry_window': 300
        }
        
        DB_CONFIG_BASE = {
            'host': '',
            'port': '',
            'user': '',
            'password': '',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        SERVER_CONFIG = {
            'http_port': 5001,
            'https_port': '',
            'ssl_cert': '',
            'ssl_key': ''
        }
        
        SITE_CONFIG = {
            'name': 'Mysql_管理',
            'logo': ''
        }
        
        save_config_to_file()
        logging.info("默认配置文件创建成功")

def save_config_to_file():
    os.makedirs(CONF_DIR, exist_ok=True)
    config = {
        'site': {
            'name': SITE_CONFIG['name'],
            'logo': SITE_CONFIG['logo']
        },
        'login': {
            'username': LOGIN_CONFIG['username'],
            'password': LOGIN_CONFIG['password']
        },
        'database': {
            'host': DB_CONFIG_BASE['host'],
            'port': DB_CONFIG_BASE['port'],
            'user': DB_CONFIG_BASE['user'],
            'password': DB_CONFIG_BASE['password']
        },
        'server': {
            'http_port': SERVER_CONFIG['http_port'],
            'https_port': SERVER_CONFIG['https_port'],
            'ssl_cert': SERVER_CONFIG['ssl_cert'],
            'ssl_key': SERVER_CONFIG['ssl_key']
        },
        'page': {
            'default_database': PAGE_CONFIG.get('default_database', ''),
            'default_table': PAGE_CONFIG.get('default_table', ''),
            'default_page_size': PAGE_CONFIG.get('default_page_size', 10)
        }
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        logging.info("配置保存成功")
        return True
    except Exception as e:
        logging.error(f"保存配置失败: {e}")
        return False

load_config()

login_attempts = {}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login')
def login():
    if 'logged_in' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    client_ip = request.remote_addr
    current_time = time.time()
    
    if client_ip in login_attempts:
        attempts = login_attempts[client_ip]
        if current_time - attempts['first_attempt_time'] > LOGIN_CONFIG['retry_window']:
            login_attempts[client_ip] = {
                'count': 0,
                'first_attempt_time': current_time,
                'lockout_until': 0
            }
            attempts = login_attempts[client_ip]
        
        if attempts['lockout_until'] > current_time:
            wait_seconds = int(attempts['lockout_until'] - current_time)
            return jsonify({
                'success': False,
                'locked': True,
                'message': '错误密码次数超限，账户已锁定。',
                'wait_seconds': wait_seconds
            })
        
        if attempts['count'] >= LOGIN_CONFIG['max_attempts']:
            if attempts['lockout_until'] > current_time:
                wait_seconds = int(attempts['lockout_until'] - current_time)
                return jsonify({
                    'success': False,
                    'locked': True,
                    'message': '错误密码次数超限，账户已锁定。',
                    'wait_seconds': wait_seconds
                })
    else:
        login_attempts[client_ip] = {
            'count': 0,
            'first_attempt_time': current_time,
            'lockout_until': 0
        }
    
    if username == LOGIN_CONFIG['username'] and password == LOGIN_CONFIG['password']:
        login_attempts[client_ip] = {
            'count': 0,
            'first_attempt_time': current_time,
            'lockout_until': 0
        }
        session['logged_in'] = True
        session['username'] = username
        session['login_time'] = time.time()
        return jsonify({'success': True})
    else:
        login_attempts[client_ip]['count'] += 1
        
        if login_attempts[client_ip]['count'] >= LOGIN_CONFIG['max_attempts']:
            login_attempts[client_ip]['lockout_until'] = current_time + LOGIN_CONFIG['lockout_duration']
            login_attempts[client_ip]['count'] = 0
            return jsonify({
                'success': False,
                'locked': True,
                'message': '错误密码次数超限，账户已锁定。',
                'wait_seconds': LOGIN_CONFIG['lockout_duration']
            })
        
        remaining = LOGIN_CONFIG['max_attempts'] - login_attempts[client_ip]['count']
        return jsonify({
            'success': False,
            'locked': False,
            'message': f'用户名或密码错误，剩余尝试次数: {remaining}'
        })

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/site-config', methods=['GET'])
def get_site_config():
    logo = SITE_CONFIG['logo']
    # 将相对路径转换为绝对路径供浏览器使用
    if logo and not (logo.startswith('http://') or logo.startswith('https://')):
        if logo.startswith('./'):
            logo = logo[1:]  # 去掉开头的 '.'，变成 '/img/xxx'
        elif not logo.startswith('/'):
            logo = '/' + logo
    config = {
        'site': {
            'name': SITE_CONFIG['name'],
            'logo': logo
        }
    }
    return jsonify(config)

@app.route('/img/<filename>')
def get_image(filename):
    img_dir = os.path.join(current_dir, 'img')
    return send_from_directory(img_dir, filename)

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    logo = SITE_CONFIG['logo']
    config = {
        'site': {
            'name': SITE_CONFIG['name'],
            'logo': logo
        },
        'login': {
            'username': LOGIN_CONFIG['username'],
            'password': LOGIN_CONFIG['password']
        },
        'database': {
            'host': DB_CONFIG_BASE['host'],
            'port': DB_CONFIG_BASE['port'],
            'user': DB_CONFIG_BASE['user'],
            'password': DB_CONFIG_BASE['password']
        },
        'server': {
            'http_port': SERVER_CONFIG['http_port'],
            'https_port': SERVER_CONFIG['https_port'],
            'ssl_cert': SERVER_CONFIG['ssl_cert'],
            'ssl_key': SERVER_CONFIG['ssl_key']
        },
        'page': {
            'default_database': PAGE_CONFIG.get('default_database', ''),
            'default_table': PAGE_CONFIG.get('default_table', ''),
            'default_page_size': PAGE_CONFIG.get('default_page_size', 10)
        }
    }
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
@login_required
def save_config():
    data = request.get_json()
    
    if 'server' in data:
        server_config = data['server']
        if 'http_port' in server_config and not server_config['http_port'].strip():
            return jsonify({'success': False, 'message': 'HTTP端口不能为空，否则应用无法访问'})
    
    if 'site' in data:
        site_config = data['site']
        if 'name' in site_config:
            SITE_CONFIG['name'] = site_config['name']
        if 'logo' in site_config:
            SITE_CONFIG['logo'] = site_config['logo']
    
    if 'login' in data:
        login_config = data['login']
        if 'username' in login_config:
            LOGIN_CONFIG['username'] = login_config['username']
        if 'password' in login_config:
            LOGIN_CONFIG['password'] = login_config['password']
    
    if 'database' in data:
        db_config = data['database']
        if 'host' in db_config:
            DB_CONFIG_BASE['host'] = db_config['host']
        if 'port' in db_config:
            DB_CONFIG_BASE['port'] = int(db_config['port']) if db_config['port'].strip() else ''
        if 'user' in db_config:
            DB_CONFIG_BASE['user'] = db_config['user']
        if 'password' in db_config:
            DB_CONFIG_BASE['password'] = db_config['password']
    
    if 'server' in data:
        server_config = data['server']
        if 'http_port' in server_config:
            SERVER_CONFIG['http_port'] = int(server_config['http_port']) if server_config['http_port'].strip() else ''
        if 'https_port' in server_config:
            SERVER_CONFIG['https_port'] = int(server_config['https_port']) if server_config['https_port'].strip() else ''
        if 'ssl_cert' in server_config:
            SERVER_CONFIG['ssl_cert'] = server_config['ssl_cert']
        if 'ssl_key' in server_config:
            SERVER_CONFIG['ssl_key'] = server_config['ssl_key']
    
    if 'page' in data:
        page_config = data['page']
        if 'default_database' in page_config:
            PAGE_CONFIG['default_database'] = page_config['default_database']
        if 'default_table' in page_config:
            PAGE_CONFIG['default_table'] = page_config['default_table']
        if 'default_page_size' in page_config:
            PAGE_CONFIG['default_page_size'] = int(page_config['default_page_size']) if page_config['default_page_size'] else 10
    
    save_config_to_file()

    return jsonify({'success': True, 'message': '配置保存成功'})

@app.route('/api/validate-server-settings', methods=['POST'])
@login_required
def validate_server_settings():
    import socket
    from datetime import datetime
    
    data = request.get_json()
    server_config = data.get('server', {})
    
    errors = []
    warnings = []
    
    http_port = server_config.get('http_port')
    https_port = server_config.get('https_port')
    ssl_cert = server_config.get('ssl_cert')
    ssl_key = server_config.get('ssl_key')
    
    if http_port:
        try:
            http_port = int(http_port)
            if http_port < 1 or http_port > 65535:
                errors.append(f'HTTP端口 {http_port} 不在有效范围内 (1-65535)')
            elif http_port != SERVER_CONFIG.get('http_port'):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', http_port))
                sock.close()
                if result == 0:
                    errors.append(f'HTTP端口 {http_port} 已被占用')
        except ValueError:
            errors.append('HTTP端口必须是有效的数字')
    
    if https_port and https_port.strip():
        try:
            https_port = int(https_port)
            if https_port < 1 or https_port > 65535:
                errors.append(f'HTTPS端口 {https_port} 不在有效范围内 (1-65535)')
            elif https_port != SERVER_CONFIG.get('https_port'):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', https_port))
                sock.close()
                if result == 0:
                    errors.append(f'HTTPS端口 {https_port} 已被占用')
        except ValueError:
            errors.append('HTTPS端口必须是有效的数字')
    
    old_ssl_cert = SERVER_CONFIG.get('ssl_cert', '')
    old_ssl_key = SERVER_CONFIG.get('ssl_key', '')
    
    ssl_cert_changed = ssl_cert != old_ssl_cert
    ssl_key_changed = ssl_key != old_ssl_key
    
    if ssl_cert_changed and ssl_cert:
        if not os.path.exists(ssl_cert):
            errors.append(f'SSL证书文件不存在: {ssl_cert}')

    if ssl_key_changed and ssl_key:
        if not os.path.exists(ssl_key):
            errors.append(f'SSL私钥文件不存在: {ssl_key}')
    
    return jsonify({
        'success': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    })

@app.route('/api/restart', methods=['POST'])
@login_required
def restart_app():
    import subprocess
    import signal

    python_exec = sys.executable
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_name = os.path.basename(__file__)
    restart_script = os.path.join(script_dir, 'restart_helper.py')
    current_pid = os.getpid()

    restart_code = f'''#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal

script_dir = "{script_dir}"
script_name = "{script_name}"
script_path = os.path.join(script_dir, script_name)
python_exec = sys.executable

if len(sys.argv) > 1:
    old_pid = int(sys.argv[1])
    
    try:
        os.kill(old_pid, signal.SIGTERM)
        time.sleep(1)
        try:
            os.kill(old_pid, 0)
            os.kill(old_pid, signal.SIGKILL)
            time.sleep(0.5)
        except ProcessLookupError:
            pass
    except ProcessLookupError:
        pass
    
    time.sleep(1)
    
    proc = subprocess.Popen(
        [python_exec, script_path],
        cwd=script_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
'''

    with open(restart_script, 'w') as f:
        f.write(restart_code)

    subprocess.Popen(
        [python_exec, restart_script, str(current_pid)],
        cwd=script_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    def delayed_exit():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=delayed_exit, daemon=True).start()

    return jsonify({'success': True, 'message': '应用即将重启'})

def init_db_pool():
    """初始化数据库连接池"""
    global db_pool
    if db_pool is None and DB_CONFIG_BASE.get('host'):
        try:
            db_pool = PooledDB(
                creator=pymysql,
                maxconnections=10,      # 最大连接数
                mincached=2,            # 最小空闲连接
                maxcached=5,            # 最大空闲连接
                maxshared=3,            # 最大共享连接
                blocking=True,          # 连接耗尽时是否阻塞等待
                maxusage=None,          # 单个连接最大使用次数(None=无限)
                setsession=[],          # 会话设置
                ping=0,                 # 连接前不检测
                **DB_CONFIG_BASE
            )
            logging.info("数据库连接池初始化成功")
        except Exception as e:
            logging.error(f"数据库连接池初始化失败: {e}")

def get_db_connection(database=None):
    """从连接池获取数据库连接"""
    global db_pool
    # 如果连接池未初始化，先初始化
    if db_pool is None:
        init_db_pool()
    
    if db_pool:
        conn = db_pool.connection()
        if database:
            # 使用SQL语句切换数据库，因为PooledDB连接对象不支持select_db方法
            cursor = conn.cursor()
            cursor.execute(f"USE `{database}`")
            cursor.close()
        return conn
    else:
        # 回退到直接连接
        config = DB_CONFIG_BASE.copy()
        if database:
            config['database'] = database
        return pymysql.connect(**config)

def init_database():
    # 表结构已经存在，不需要创建
    pass

@app.route('/')
@login_required
def index():
    return render_template('index.html', data=[], tables=[], database_name='')

@app.route('/api/databases', methods=['GET'])
def get_databases():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW DATABASES")
            result = cursor.fetchall()
            databases = []
            for row in result:
                if isinstance(row, dict):
                    db_name = list(row.values())[0]
                else:
                    db_name = row[0]
                if db_name not in ['information_schema', 'mysql', 'performance_schema', 'sys']:
                    databases.append(db_name)
        return jsonify(databases)
    finally:
        connection.close()

@app.route('/api/tables', methods=['GET'])
def get_tables():
    database = request.args.get('database')
    if not database:
        return jsonify([])
    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            result = cursor.fetchall()
            if result and isinstance(result[0], dict):
                tables = [list(table.values())[0] for table in result]
            else:
                tables = [table[0] for table in result]
        return jsonify(tables)
    finally:
        connection.close()

@app.route('/api/table/<table_name>/structure', methods=['GET'])
def get_table_structure(table_name):
    database = request.args.get('database')
    if not database:
        return jsonify([])
    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DESCRIBE {table_name}")
            result = cursor.fetchall()
            structure = []
            for row in result:
                if isinstance(row, dict):
                    structure.append({
                        'field': row.get('Field'),
                        'type': row.get('Type'),
                        'null': row.get('Null'),
                        'key': row.get('Key'),
                        'default': row.get('Default'),
                        'extra': row.get('Extra')
                    })
                else:
                    structure.append({
                        'field': row[0],
                        'type': row[1],
                        'null': row[2],
                        'key': row[3],
                        'default': row[4],
                        'extra': row[5]
                    })
            
            cursor.execute(f"SELECT COLUMN_NAME, COLUMN_COMMENT FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s", (database, table_name))
            comments_result = cursor.fetchall()
            comments = {}
            if comments_result:
                if isinstance(comments_result[0], dict):
                    for item in comments_result:
                        comments[item.get('COLUMN_NAME', '')] = item.get('COLUMN_COMMENT', '')
                else:
                    for item in comments_result:
                        comments[item[0]] = item[1] if len(item) > 1 else ''
            
            for field in structure:
                field_name = field['field']
                field['comment'] = comments.get(field_name, '')
        return jsonify(structure)
    finally:
        connection.close()

@app.route('/api/table/<table_name>/data', methods=['GET'])
def get_table_data(table_name):
    database = request.args.get('database')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('pageSize', 20))
    
    if not database:
        return jsonify({'data': [], 'total': 0, 'page': 1, 'pageSize': page_size})
    
    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            # 获取记录总数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total = cursor.fetchone()
            total = total['COUNT(*)'] if isinstance(total, dict) else total[0]
            
            # 分页查询
            offset = (page - 1) * page_size
            cursor.execute(f"SELECT * FROM {table_name} LIMIT %s OFFSET %s", (page_size, offset))
            data = cursor.fetchall()
        
        return jsonify({
            'data': data,
            'total': total,
            'page': page,
            'pageSize': page_size
        })
    finally:
        connection.close()

@app.route('/api/table/<table_name>/data', methods=['POST'])
def add_table_data(table_name):
    data = request.get_json()
    database = data.get('database')
    if not database:
        return jsonify({'success': False, 'message': '数据库名称不能为空'})
    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            field_order = data.get('fieldOrder', [])
            insert_data = {k: v for k, v in data.items() if k not in ['database', 'fieldOrder']}
            if not insert_data:
                return jsonify({'success': False, 'message': '没有需要添加的数据'})
            fields = list(insert_data.keys())
            values = list(insert_data.values())
            placeholders = ', '.join(['%s'] * len(values))
            field_names = ', '.join(fields)
            sql = f"INSERT INTO {table_name} ({field_names}) VALUES ({placeholders})"
            cursor.execute(sql, values)
        connection.commit()
        add_history_record('添加', '成功', database, table_name, insert_data, field_order)
        return jsonify({'success': True, 'message': '数据添加成功'})
    finally:
        connection.close()

@app.route('/api/table/<table_name>/data/<id>', methods=['PUT'])
def update_table_data(table_name, id):
    data = request.get_json()
    database = data.get('database')
    primary_key_field = data.get('primaryKeyField', 'id')
    if not database:
        return jsonify({'success': False, 'message': '数据库名称不能为空'})
    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            field_order = data.get('fieldOrder', [])
            update_data = {k: v for k, v in data.items() if k not in ['database', 'primaryKeyField', 'fieldOrder']}
            if not update_data:
                return jsonify({'success': False, 'message': '没有需要更新的数据'})
            set_clause = ', '.join([f"{field}=%s" for field in update_data.keys()])
            values = list(update_data.values()) + [id]
            sql = f"UPDATE {table_name} SET {set_clause} WHERE {primary_key_field}=%s"
            cursor.execute(sql, values)
        connection.commit()
        add_history_record('更新', '成功', database, table_name, update_data, field_order)
        return jsonify({'success': True, 'message': '数据更新成功'})
    finally:
        connection.close()

@app.route('/api/table/<table_name>/data/<id>', methods=['DELETE'])
def delete_table_data(table_name, id):
    database = request.args.get('database')
    primary_key_field = request.args.get('primaryKeyField', 'id')
    if not database:
        return jsonify({'success': False, 'message': '数据库名称不能为空'})
    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table_name} WHERE {primary_key_field} = %s", (id,))
            record = cursor.fetchone()
            cursor.execute(f"DESCRIBE {table_name}")
            field_order = [row[0] if isinstance(row, (list, tuple)) else row.get('Field') for row in cursor.fetchall()]
            cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key_field} = %s", (id,))
        connection.commit()
        add_history_record('删除', '成功', database, table_name, record, field_order)
        return jsonify({'success': True, 'message': '数据删除成功'})
    finally:
        connection.close()

@app.route('/api/table/<table_name>/data/batch', methods=['DELETE'])
def batch_delete_table_data(table_name):
    data = request.get_json()
    database = data.get('database')
    primary_key_field = data.get('primaryKeyField', 'id')
    ids = data.get('ids', [])
    field_order = data.get('fieldOrder', [])

    if not database:
        return jsonify({'success': False, 'message': '数据库名称不能为空'})
    if not ids or len(ids) == 0:
        return jsonify({'success': False, 'message': '没有要删除的记录'})

    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            placeholders = ', '.join(['%s'] * len(ids))
            cursor.execute(f"SELECT * FROM {table_name} WHERE {primary_key_field} IN ({placeholders})", ids)
            records = cursor.fetchall()
            cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key_field} IN ({placeholders})", ids)
        connection.commit()
        for record in records:
            add_history_record('批量删除', '成功', database, table_name, record, field_order)
        return jsonify({'success': True, 'message': f'成功删除 {len(ids)} 条记录'})
    finally:
        connection.close()

@app.route('/api/execute-sql', methods=['POST'])
def execute_sql():
    data = request.get_json()
    sql = data.get('sql', '').strip()
    database = data.get('database', '')
    
    if not sql:
        return jsonify({'success': False, 'message': 'SQL语句不能为空'})
    
    if not database:
        return jsonify({'success': False, 'message': '请先选择一个数据库'})
    
    connection = get_db_connection(database)
    try:
        with connection.cursor() as cursor:
            # 分割多条SQL语句
            sql_statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
            
            if len(sql_statements) == 1:
                # 单条SQL语句
                cursor.execute(sql_statements[0])
                
                # 检查是否是查询语句
                if sql_statements[0].strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    # 转换结果为字典列表
                    if result:
                        if isinstance(result[0], dict):
                            data = result
                        else:
                            # 获取列名
                            columns = [desc[0] for desc in cursor.description]
                            data = [dict(zip(columns, row)) for row in result]
                    else:
                        data = []
                    return jsonify({'success': True, 'data': data})
                else:
                    # 非查询语句，返回影响行数
                    affected_rows = cursor.rowcount
                    connection.commit()
                    return jsonify({'success': True, 'affected_rows': affected_rows})
            else:
                # 多条SQL语句
                results = []
                total_affected_rows = 0
                
                for stmt in sql_statements:
                    cursor.execute(stmt)
                    
                    if stmt.strip().upper().startswith('SELECT'):
                        result = cursor.fetchall()
                        if result:
                            if isinstance(result[0], dict):
                                data = result
                            else:
                                columns = [desc[0] for desc in cursor.description]
                                data = [dict(zip(columns, row)) for row in result]
                        else:
                            data = []
                        results.append({'type': 'select', 'data': data})
                    else:
                        total_affected_rows += cursor.rowcount
                
                connection.commit()
                
                if results:
                    return jsonify({'success': True, 'results': results, 'affected_rows': total_affected_rows})
                else:
                    return jsonify({'success': True, 'affected_rows': total_affected_rows})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        connection.close()

@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    history = load_history()
    return jsonify({
        'data': history,
        'total': len(history)
    })

@app.route('/api/history/export', methods=['GET'])
@login_required
def export_history():
    from flask import Response
    history = load_history()
    import io
    output = io.StringIO()
    output.write('完成状态,操作类型,数据库,表名,记录数据,操作时间\n')
    for record in history:
        record_data_str = ''
        if record.get('record_data'):
            field_order = record.get('field_order', [])
            if isinstance(record['record_data'], dict):
                if field_order and isinstance(field_order, list):
                    ordered_data = [(k, record['record_data'].get(k, '')) for k in field_order]
                else:
                    ordered_data = list(record['record_data'].items())
                record_data_str = '; '.join([f"{k}={v}" for k, v in ordered_data])
            else:
                record_data_str = str(record['record_data'])
        output.write(f"{record.get('status', '')},{record.get('action_type', '')},{record.get('database', '')},{record.get('table', '')},\"{record_data_str}\",{record.get('timestamp', '')}\n")
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=history.csv'}
    )

@app.route('/api/history/clear', methods=['POST'])
@login_required
def clear_history():
    try:
        save_history([])
        return jsonify({'success': True, 'message': '历史记录已清空'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def run_app(ssl_cert=None, ssl_key=None):
    """
    运行应用，同时启用 HTTP 和 HTTPS
    
    Args:
        ssl_cert (str): SSL 证书文件路径
        ssl_key (str): SSL 私钥文件路径
    """
    init_database()

    http_port = SERVER_CONFIG.get('http_port', 5001)
    https_port = SERVER_CONFIG.get('https_port', 5002)
    
    # 启动 HTTP 服务器
    def start_http_server():
        logging.info(f"Starting HTTP server on port {http_port}...")
        app.run(host='0.0.0.0', port=http_port, debug=False, use_reloader=False)
    
    # 启动 HTTPS 服务器（如果提供了证书）
    def start_https_server():
        if ssl_cert and ssl_key:
            try:
                # 配置 SSL 上下文
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(ssl_cert, ssl_key)
                
                logging.info(f"Starting HTTPS server on port {https_port}...")
                app.run(host='0.0.0.0', port=https_port, debug=False, use_reloader=False, ssl_context=context)
            except Exception as e:
                logging.error(f"Failed to start HTTPS server: {str(e)}")
                logging.error("SSL certificate may be invalid or path is incorrect")
        else:
            logging.info("HTTPS server not started (no SSL certificate provided)")
    
    # 创建并启动线程
    http_thread = threading.Thread(target=start_http_server)
    https_thread = threading.Thread(target=start_https_server)
    
    http_thread.daemon = True
    https_thread.daemon = True
    
    http_thread.start()
    https_thread.start()
    
    # 等待线程结束
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")

if __name__ == '__main__':
    ssl_cert = SERVER_CONFIG.get('ssl_cert', '')
    ssl_key = SERVER_CONFIG.get('ssl_key', '')
        
    run_app(ssl_cert, ssl_key)