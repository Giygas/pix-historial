from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import time

import requests

app = FastAPI()
scheduler = BackgroundScheduler()


from .database import tracker


@app.get("/")
def root():
    return requestData()


@app.get("/{appName}")
def getAppData(appName: str) -> str:
    # TODO: logic for getting the historic data for this app
    # use HTTPexception for managing invalid data
    print("this thing is ", {appName})
    savedId = tracker.saveData()
    print("data saved: ", savedId)
    return appName


def print_time():
    print(f"The current time is {time.ctime()}")


def requestData():
    response = requests.get("https://pix.ferminrp.com/quotes")
    return response.json()


# scheduler.add_job(print_time, CronTrigger(minute="*/1"))  # Every minute
# scheduler.start()
