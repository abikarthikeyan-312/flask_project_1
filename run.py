from dotenv import load_dotenv
load_dotenv()  # 👈 THIS LINE

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
