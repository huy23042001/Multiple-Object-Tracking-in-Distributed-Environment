from mysql.connector import connect

class MySQLBuilder:
    def __init__(self):
        # self.mydb = connect(
        #     host="localhost",
        #     user="admin",
        #     password="password",
        #     database="test") 
        self.mydb = connect(
            host="localhost",
            user="hduser",
            password="hduser@123",
            database="object_tracking") 
        
    def execute(self, query_str):
        cursor = self.mydb.cursor()
        cursor.execute(query_str)
        count = cursor.rowcount
        if (count > 0):
            return 
        else:
            data = cursor.fetchall()
            self.mydb.close()
            return data
            
        

# db = MySQLBuilder()
# print(db.execute("select * from cameras"))

# def save_image():
#     mydb = connect(
#         host="localhost",
#         user="admin",
#         password="password",
#         database="test") 
#     cursor = mydb.cursor()
#     query = "SELECT object_amount FROM event_logs where camera_id = %s ORDER BY ID DESC LIMIT 1"
#     cursor.execute(query, [1])
#     data = cursor.fetchall()
#     count = cursor.rowcount
#     if (count > 0 and data[0][0] == 3):
#         print("false")
#     sql = "INSERT INTO frame (camera_id, send_time, data) VALUES (%s, %s, %s)"
    
#     mydb.commit()
#     mydb.close()

# save_image()