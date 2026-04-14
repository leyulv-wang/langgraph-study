from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


# 接口： 返回一张图片内容
@app.get("/file")
async def get_file():
    path = "./files/1.jpeg"
    return FileResponse(path)
