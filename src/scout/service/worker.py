from scout.service.main import searches, work_forever

if __name__ == "__main__":
    work_forever(searches())
