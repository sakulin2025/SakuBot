import uvicorn

uvicorn.run("sakubot.web:app", host="0.0.0.0", port=6190, workers=1, access_log=False)
