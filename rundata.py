import logging.config
import extractdata
import config

logging.config.fileConfig('conf/logging.conf')
logger = logging.getLogger('RunData')

logger.info('Job Start')

just_join_it = extractdata.DataProcessingJJI(
                    url_list=config.URLS_JUST_JOIN_IT,
                    main_url=config.MAIN_JUST_JOIN_IT,
                    source_name='justjoinit'
                )
just_join_it.run()

