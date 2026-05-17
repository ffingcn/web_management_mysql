# MySQL Web 管理工具
<img width="1674" height="1006" alt="image" src="https://github.com/user-attachments/assets/0be2aca9-3d9b-4f81-85c6-8aaf72c2498d" />
一个基于 Flask 的轻量级 MySQL 数据库管理工具，提供直观的 Web 界面用于管理 MySQL 数据库。

## 功能特性

- 📊 **数据库管理** - 查看所有数据库和数据表
- 📋 **表结构** - 查看和管理表的字段结构
- ✏️ **数据操作** - 支持数据的增删改查操作
- 📝 **SQL执行** - 支持执行 SQL 语句（支持多条）
- 🔐 **用户认证** - 登录认证，支持密码锁定机制
- ⚙️ **配置管理** - 可视化配置数据库连接、服务器设置等
- 🔌 **连接池** - 使用连接池管理数据库连接
- 🚀 **HTTP/HTTPS** - 支持 HTTP 和 HTTPS 协议

## 技术栈

- **框架**: Flask 3.1.2
- **数据库驱动**: PyMySQL 1.1.2
- **连接池**: DBUtils 3.0.3
- **缓存**: Flask-Caching 2.1.0
- **压缩**: Flask-Compress 1.17

## 快速开始

**默认登录凭证:**
- 用户名: `admin`
- 密码: `123456`
- 应用启动后访问: `http://localhost:5001`
### 方法一： 直接运行
```
#环境： Python 3.10+

#验证依赖
pip install -r requirements.txt

#运行脚本
python app.py
```





### 方法一： 直Docker 部署
-  使用docker compose文件本地构建或docke pull 拉取镜像
```bash
version: '3.8'

services:
  web_management_mysql:
    build: .
    image: ffingcn/web_management_mysql:1.0.0
    container_name: web_management_mysql
    restart: always
    ports:
      - "5001:5001"
      - "5002:5002"
    volumes:
      - ./conf:/app/conf
      - ./log:/app/log
      - ./ssl:/app/ssl
      - ./img:/app/img
    environment:
      - TZ=Asia/Shanghai
    networks:
      - web_management_mysql
    privileged: true

networks:
  web_management_mysql:
    driver: bridge
```



## 项目结构

```
├── app.py              # 主应用文件
├── requirements.txt    # Python 依赖
├── docker-compose.yml  # Docker Compose 配置
├── dockerfile          # Docker 构建文件
├── restart_helper.py   # 重启辅助脚本
├── img/                # 图片资源目录
│   └── logo.png
├── ssl/                # SSL 证书目录
│   ├── server.crt
│   └── server.key
├── templates/          # HTML 模板目录
│   ├── index.html      # 主页面
│   └── login.html      # 登录页面
├── conf/               # 配置文件目录（运行时自动创建）
│   └── config.json     # 配置文件
└── log/                # 日志目录（运行时自动创建）
    └── run.log         # 应用日志
```

## 配置说明

配置文件位于 `conf/config.json`，第一次运行自动创建。

包含以下配置项：

```json
{
    "site": {
        "name": "Mysql_管理",
        "logo": "./img/logo.png"
    },
    "login": {
        "username": "admin",
        "password": "123456"
    },
    "database": {
        "host": "localhost",
        "port": "3306",
        "user": "root",
        "password": "password"
    },
    "server": {
        "http_port": 5001,
        "https_port": 5002,
        "ssl_cert": "./ssl/server.crt",
        "ssl_key": "./ssl/server.key"
    }
}
```

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| site.name | 站点名称 | Mysql_管理 |
| site.logo | 站点 Logo 路径 | - |
| login.username | 登录用户名 | admin |
| login.password | 登录密码 | 123456 |
| database.host | MySQL 主机地址 | - |
| database.port | MySQL 端口 | 3306 |
| database.user | MySQL 用户名 | - |
| database.password | MySQL 密码 | - |
| server.http_port | HTTP 服务端口 | 5001 |
| server.https_port | HTTPS 服务端口（留空则不启用） | - |
| server.ssl_cert | SSL 证书路径 | - |
| server.ssl_key | SSL 私钥路径 | - |

## API 接口

### 认证接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/login` | POST | 用户登录 |
| `/api/logout` | POST | 用户登出 |

### 配置接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/config` | GET | 获取配置 |
| `/api/config` | POST | 保存配置 |
| `/api/site-config` | GET | 获取站点配置 |
| `/api/validate-server-settings` | POST | 验证服务器设置 |
| `/api/restart` | POST | 重启应用 |

### 数据库接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/databases` | GET | 获取数据库列表 |
| `/api/tables` | GET | 获取数据表列表 |
| `/api/table/{table_name}/structure` | GET | 获取表结构 |
| `/api/table/{table_name}/data` | GET | 获取表数据（分页） |
| `/api/table/{table_name}/data` | POST | 添加数据 |
| `/api/table/{table_name}/data/{id}` | PUT | 更新数据 |
| `/api/table/{table_name}/data/{id}` | DELETE | 删除数据 |
| `/api/execute-sql` | POST | 执行 SQL 语句 |

## 安全特性

- 登录失败次数限制（默认 3 次）
- 账户锁定机制（默认 5 分钟）
- 会话管理
- 支持 HTTPS 加密传输

## 使用说明

1. **登录系统**: 访问首页后，使用默认凭证登录
2. **配置数据库**: 登录后进入设置页面，配置 MySQL 连接信息
3. **管理数据库**: 配置完成后即可查看和管理数据库

## 注意事项

- 首次运行时会自动创建默认配置文件
- 配置文件中的密码以明文形式存储，请确保文件权限安全
- 建议在生产环境中使用 HTTPS
- 请定期备份数据库和配置文件

