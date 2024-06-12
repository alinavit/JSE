import psycopg2
import db_info
import logging.config

logging.config.fileConfig("C:\\Users\\48575\\PycharmProjects\\JSE4\\conf\\logging.conf")
logger = logging.getLogger('databaseLogger')


class FlyDatabase:
    def __init__(self, source: str, data):
        self.source = source
        self.data = data
        self.host = db_info.HOST
        self.database = db_info.DATABASE
        self.user = db_info.USER
        self.password = db_info.PASSWORD
        self.conn = None
        self.cur = None

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )

            self.cur = self.conn.cursor()
            logger.info(f'Connected to {self.database} database')
        except Exception as e:
            logger.critical(f'Error in connection to {self.database}')
            logger.exception(f'Exception {e}')

    def disconnect(self):
        if self.conn.closed == 0:
            self.conn.close()
            logger.info(f'Disconnected from {self.database} database')
        else:
            logger.info(f'Cannot disconnect. {self.database} is already disconnected')

    def write(self):
        self.connect()

        for i in self.data:
            if isinstance(i, dict):
                sql_statement = '''
                                    INSERT INTO positions_test (
                                                        load_id,
                                                        source, 
                                                        reg_timestamp, 
                                                        f_time, 
                                                        f_flight, 
                                                        f_start_airport, 
                                                        f_dest_airport, 
                                                        f_state
                                                        )
                                                VALUES (
                                                        nextval('load_id_seq'),
                                                        %s,
                                                        CURRENT_TIMESTAMP,
                                                        %s,
                                                        %s,
                                                        %s,
                                                        %s,
                                                        %s
                                                        )                                      
                '''
                try:
                    sql_values = (self.source,
                                  i['date'],
                                  i['flight'],
                                  i['start_airport'],
                                  i['destination'],
                                  i['status']
                                  )
                except KeyError as e:
                    with open(f'files\\error_rows_{self.source}.txt', 'a+', encoding='utf-8') as file:
                        file.write(str(i) + '\n')
                        logger.critical('KeyError: Missing key in data dictionary')
                        logger.exception(f'Exception : {e}')
                    continue
                except Exception as e:
                    with open(f'files\\error_rows_{self.source}.txt', 'a+', encoding='utf-8') as file:
                        file.write(str(i) + '\n')
                    logger.critical('Error: Something wrong with the data. Values stored to ')
                    logger.exception(f'Exception : {e}')

                try:
                    self.cur.execute(sql_statement, sql_values)
                    self.conn.commit()

                except Exception as e:
                    with open(f'files\\error_rows_{self.source}.txt', 'a+', encoding='utf-8') as file:
                        file.write(str(sql_values) + '\n')

                    logger.critical('Error executing SQL statement')
                    logger.exception(f'Exception: {e}')
                    self.conn.rollback()
            else:
                logger.warning('Data provided unexpectedly. The data has to be a list of dictionaries.')

        self.conn.close()
