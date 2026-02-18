# Flask Question Paper Generator

This repository contains the **qp_copy_11** Flask application which manages schools, departments, subjects, question banks, and generates examination papers. It provides separate admin and staff portals with real-time analytics, user management, paper generation, and more.

## 🚀 Features

- Admin dashboard with system analytics
- Manage schools, departments, subjects, patterns, and weightages
- Question bank and master archives
- Paper generation and activation workflows
- Staff portal for generating papers, scrutiny, and viewing archives
- Custom UI with collapsible sidebar and responsive design

## 🛠️ Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/abikarthikeyan-312/flask_project_1.git
   cd flask_project_1
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   venv\Scripts\activate    # Windows
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Copy `.env.example` (if available) or create a `.env` file with at least:
   ```ini
   FLASK_ENV=development
   SECRET_KEY=your-secret-key
   DATABASE_URL=mysql+pymysql://username:password@localhost/dbname
   ```

4. **Initialize the database:**
   ```bash
   flask db upgrade   # or use the migrations folder
   ```

5. **Run the application:**
   ```bash
   python run.py
   ```

6. **Access the app:**
   Open `http://127.0.0.1:5000` in your browser.

## 📁 Project Structure

```
app/             # application package
  models/        # SQLAlchemy models
  routes/        # blueprints for admin/staff/api
  services/      # business logic
  templates/     # HTML templates
  static/        # CSS & JS assets
config.py        # configuration
run.py           # application entry point
migrations/      # database migrations
```

## 🤝 Contributing
Feel free to fork the repo and submit pull requests. Please ensure new features follow the existing code style and add tests where appropriate.

## 📄 License
Specify your project license here.
