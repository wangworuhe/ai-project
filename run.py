# from app import create_app
from backend import create_app

print("Creating app...")
app = create_app()
print("App created.")

if __name__ == '__main__':
    print("Running app...")
    app.run(debug=True)
