from multiprocessing import Process
import logging.config

import database
import extractdata
import config2
from timeit import default_timer

logging.config.fileConfig("C:\\Users\\48575\\PycharmProjects\\JSE4\\conf\\logging.conf")
logger = logging.getLogger('RunData')

logger.info('Job Start')

if __name__ == "__main__":
    start = default_timer()

    just_join_it = extractdata.DataProcessingJJI(
                        url_list=config2.URLS_JUST_JOIN_IT,
                        main_url=config2.MAIN_JUST_JOIN_IT,
                        source_name='justjoinit')

    stepstone = extractdata.DataProcessingST(
                       url_list=config2.URLS_STEPSTONE,
                       main_url=config2.MAIN_ST,
                       source_name='stepstone',
                       selenium=True,
                       cookies_selector=config2.COOKIES_ST
                        )

    nofluffjobs = extractdata.DataProcessingNFJ(
                   url_list=config2.URLS_NFJ,
                   main_url=config2.MAN_NFJ,
                   source_name='nofluffjobs'
                    )

    pracujpl = extractdata.DataProcessingPR(
       url_list=config2.URLS_PRPL,
       main_url=config2.MAIN_PRPL,
       source_name='pracujpl'
    )

    processes = [
        Process(target=just_join_it.run),
        Process(target=nofluffjobs.run),
        Process(target=pracujpl.run)
    ]

    for process in processes:
        process.start()

    for every in processes:
        every.join()

    database.JSEDatabase().data_adjust()
    database.JSEDatabase().csv_download()

    stop = default_timer()
    print(stop-start)
