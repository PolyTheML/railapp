#!/bin/bash
# setup.sh - Django Database Manager Setup Script

echo "🚀 Setting up Django Database Manager..."

# Create project directory
echo "📁 Creating project directory..."
mkdir -p django-db-manager
cd django-db-manager

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install django djangorestframework django-cors-headers
pip install psycopg2-binary mysql-connector-python sqlalchemy
pip install pandas openpyxl python-decouple whitenoise gunicorn

# Create Django project
echo "🏗️ Creating Django project..."
django-admin startproject dbmanager .

# Create app
echo "📱 Creating Django app..."
python manage.py startapp database_tool

# Create directories
echo "📂 Creating template directories..."
mkdir -p templates/registration
mkdir -p database_tool/templates/database_tool
mkdir -p static
mkdir -p media

# Create .env file
echo "⚙️ Creating environment file..."
cat > .env << 'EOF'
SECRET_KEY=django-insecure-your-secret-key-change-this-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database settings
DATABASE_URL=sqlite:///db.sqlite3

# For production databases
POSTGRES_DB=your_db
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
EOF

# Create requirements.txt
echo "📋 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
Django>=4.2.0
djangorestframework>=3.14.0
django-cors-headers>=4.0.0
psycopg2-binary>=2.9.0
mysql-connector-python>=8.0.0
sqlalchemy>=2.0.0
pandas>=2.0.0
openpyxl>=3.1.0
python-decouple>=3.8
whitenoise>=6.5.0
gunicorn>=21.2.0
EOF

echo "✅ Django project structure created!"
echo ""
echo "📝 Next steps:"
echo "1. Copy the provided Python files into their respective locations:"
echo "   - database_tool/models.py"
echo "   - database_tool/views.py" 
echo "   - database_tool/forms.py"
echo "   - database_tool/database_connectors.py"
echo "   - database_tool/admin.py"
echo "   - database_tool/urls.py"
echo "   - dbmanager/settings.py"
echo "   - dbmanager/urls.py"
echo "   - templates/registration/login.html"
echo ""
echo "2. Run migrations:"
echo "   python manage.py makemigrations"
echo "   python manage.py migrate"
echo ""
echo "3. Create superuser:"
echo "   python manage.py createsuperuser"
echo ""
echo "4. Run development server:"
echo "   python manage.py runserver"
echo ""
echo "🎉 Your Django Database Manager will be ready!"