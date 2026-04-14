from fastapi import FastAPI, Request, Response

#中间件是由下而上的执行的，先执行最后的中间件，再执行第一个中间件，从客户端到服务器，先1后2，然后返回先2后1，中间件是针对所有路由的，不是针对某个路由的，特定接口使用的是依赖注入，而不是中间件
def setup_middlewares(app: FastAPI) -> None:
    @app.middleware("http")
    async def middleware2(request: Request, call_next) -> Response:
        print("中间件2 start")
        response = await call_next(request)
        print("中间件2 end")
        return response

    @app.middleware("http")
    async def middleware1(request: Request, call_next) -> Response:
        print("中间件1 start")
        response = await call_next(request)
        print("中间件1 end")
        return response
