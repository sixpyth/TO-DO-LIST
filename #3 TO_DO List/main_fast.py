# python -m uvicorn main_fast:app --reload
import sqlite3
from fastapi import FastAPI, Request, Form, Response, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uuid

templates = Jinja2Templates(directory="templates")


app = FastAPI()
app.mount("/static",StaticFiles(directory="static"), name="static")



conn = sqlite3.connect("basement.db",check_same_thread=False)

def get_db():
     conn = sqlite3.connect("basement.db",check_same_thread=False)
     conn.row_factory = sqlite3.Row
     return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            user_password TEXT
        )""")
        conn.commit()
        cursor.execute("SELECT * FROM users")
        cursor.fetchall()


        conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
                     session_id TEXT PRIMARY KEY,
                     user_id INTEGER,
                     FOREIGN KEY (user_id) REFERENCES users (id)
                     
     )""")
        conn.commit()
        cursor.fetchall()


        conn.execute("""CREATE TABLE IF NOT EXISTS todos(
                     task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                     task TEXT,
                     done INTEGER,
                     user_id INTEGER,
                     created_at TIMESTAMP DEFAULT CURRENT_TIME, 
                     FOREIGN KEY (user_id) REFERENCES users (id))
                     """)
        try:
             cursor.execute("ALTER TABLE todos ADD COLUMN priority INTEGER DEFAULT 0;")
        except sqlite3.OperationalError as e:
             print("Ошибка",e)
        

             
        conn.commit()
        cursor.execute("SELECT * FROM todos")
        tasks = cursor.fetchall()
        
     
        
     #    print(cursor.fetchall())
        

init_db()


@app.get("/profile")
def show_profile(request:Request):
     return templates.TemplateResponse("profile.html",{"request":request})



@app.get("/")
def main(request:Request):
     with get_db() as conn:
          cursor = conn.cursor()
          
          session_id = request.cookies.get("session_id")
          user_name = None
          if session_id:
               cursor.execute("SELECT user_id FROM sessions WHERE session_id = ?", (session_id,))
               row = cursor.fetchone()
               if row:
                    cursor.execute("SELECT user_name FROM users WHERE id = ?", (row["user_id"],))
                    user_row = cursor.fetchone()
                    if user_row:
                         user_name = user_row["user_name"]

                         

          sessions = cursor.execute("SELECT user_id FROM sessions WHERE session_id = ?",(session_id,)).fetchone()
          conn.commit


          tasks = cursor.execute("""
               SELECT todos.task, users.user_name,todos.task_id, todos.done,todos.priority, todos.created_at
               FROM todos
               JOIN users ON todos.user_id = users.id
               """).fetchall()
          
          created = cursor.execute("SELECT created_at FROM todos").fetchone()
          conn.commit
          
          return templates.TemplateResponse("main_page.html", {"request":request,"created":created, "tasks":tasks, "sessions":sessions,"user_name":user_name})


@app.post("/registration",response_class=HTMLResponse)
def registr(request:Request,user_name:str = Form (...),user_password: str = Form(...)):
    
    
    if len(user_password)<5:
         return templates.TemplateResponse(
                    "main_page.html", {"request": request, "error": "Ваш пароль должен содержать не меньше 5 символов"}
                )
    
    with get_db() as conn:
     cursor = conn.cursor()
     old_user = cursor.execute("SELECT * FROM users").fetchall()
     if " " in user_password:
           return templates.TemplateResponse(
                    "main_page.html", {"request": request, "error": "Убери пробел"}
                )

     # old_user = cursor.execute("SELECT * FROM users WHERE user_name = ?",(user_name,)).fetchall()
     for i in old_user:
          if i["user_name"] == user_name:
                return templates.TemplateResponse(
                    "main_page.html", {"request": request, "error": "Пользователь с таким именем уже существует"}
                )

     cursor.execute("INSERT INTO users ('user_name','user_password') VALUES (?,?)",(user_name,user_password))
     cursor.execute("SELECT * FROM users")
     conn.commit()
     for row in cursor:
          print(dict(row))
     print(cursor.fetchall())
     
     return RedirectResponse("/", status_code=303)




@app.post("/login")
def login(request:Request,response:Response,user_name: str = Form(...),user_password: str = Form(...)):
     with get_db() as conn:

          cursor = conn.cursor()
          user = cursor.execute("SELECT * FROM users WHERE user_name = ?",(user_name,)).fetchone()
          password = cursor.execute("SELECT * FROM users WHERE user_password = ?",(user_password,)).fetchone()
          #создаем куки нахуй
          session_id = str(uuid.uuid4())
          if user and user["user_name"] == user_name:
               if password and password["user_password"] == user_password:
                    print(f"{user["id"],"Пользователь под ником:",user["user_name"]} Вошел в сеть")
                    print(session_id)
                    cursor.execute("INSERT INTO sessions (session_id,user_id) VALUES (?,?)",(session_id,user["id"]))
                    conn.commit()
                    response = RedirectResponse("/", status_code=303)
                    response.set_cookie(
                         key="session_id",
                         value=session_id,
                         httponly=True,
                         secure=False,
                         samesite="lax",
                         
                    )   
                    return response
               else:
                    return templates.TemplateResponse(
                    "main_page.html", {"request": request, "error": "Неправильно введен пароль"} )
               
          else:
               return templates.TemplateResponse(
                    "main_page.html", {"request": request, "error": "Пользователь не найден"} )
          



@app.get("/exit")
def logout(response:Response,request:Request):
     
     response = templates.TemplateResponse("main_page.html",{"request":request})
     response.delete_cookie("session_id")
     return response 




@app.post("/add_task")
def new_task(request:Request,task:str = Form(...)):
     session_id = request.cookies.get("session_id")
     if not session_id:
           return templates.TemplateResponse(
                    "main_page.html", {"request": request, "error": "Войдите в аккаунт"}
                )
     
     with get_db() as conn:
          cursor = conn.cursor()
          session = cursor.execute("SELECT user_id FROM sessions WHERE session_id = ?", (session_id,))
          
          row = cursor.fetchone()
          user_id = row["user_id"]
          cursor.execute("SELECT user_name FROM users WHERE id = ?",(user_id,))
          user_row = cursor.fetchone()
          user_name = user_row["user_name"]

          
          cursor.execute("INSERT INTO todos ('task','done','user_id') VALUES (?,?,?)",(task,0,user_id))
         
          tasks = cursor.execute("SELECT * FROM todos")
          for i in tasks:
               print(dict(i))     
          return RedirectResponse("/",status_code=303)
             
          # return templates.TemplateResponse(
          #      "main_page.html",{"request":request,"user_name":user_name}
          # )

@app.post("/delete/{task_id}")
def delete_task(task_id:int):
     with get_db() as conn:
          cursor = conn.cursor()
          cursor.execute("DELETE FROM todos WHERE task_id = ?",(task_id,))
          conn.commit()
          return RedirectResponse("/", status_code=303)


@app.post("/edit/{task_id}")
def edit_task(task_id:int, new_text: str = Form(...)):
    with get_db() as conn:
          cursor = conn.cursor()
          cursor.execute("UPDATE todos SET task = ? WHERE task_id = ?",(new_text,task_id))
          conn.commit()

          return RedirectResponse("/", status_code=303)
            


@app.post("/done/{task_id}")
def done_task(task_id:int):
     with get_db() as conn:
          cursor = conn.cursor()
          cursor.execute("""
                         UPDATE todos 
                         SET done = CASE
                              WHEN done = 0 THEN 1
                                   ELSE 0
                              END  
                         WHERE task_id = ?""",(task_id,))
          conn.commit()
          show_done = cursor.execute("SELECT * FROM todos")
          for row in show_done:
               print(dict(row))  # теперь работает нормально   
               print("rowcount:", cursor.rowcount)  # покажет, сколько строк обновилось 
          

     return RedirectResponse("/", status_code=303)



@app.post("/priority/{task_id}")
def set_priority(task_id:int,priority: str=Form(...)):
     with get_db() as conn:
          cursor = conn.cursor()
          cursor.execute("""UPDATE todos set priority = ? WHERE task_id = ?""",(priority,task_id))
          show = cursor.execute("SELECT * FROM todos").fetchall()
          for i in show:
               print(dict(i))
          conn.commit()
     return RedirectResponse("/",status_code=303)





# @app.post("/order")
# def set_order():
#      with get_db() as conn:
#           cursor = conn.cursor()
#           cursor.execute("SELECT task_id, priority FROM todos ORDER BY priority DESC")
#           tasks = cursor.fetchall()
#           for i in tasks:
#                print(dict(i))
#           return RedirectResponse("/",status_code=303)





