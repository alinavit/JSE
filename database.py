import pandas as pd
import psycopg2
import db_info
import logging.config

logging.config.fileConfig("C:\\Users\\48575\\PycharmProjects\\JSE4\\conf\\logging.conf")
logger = logging.getLogger('databaseLogger')


class JSEDatabase:
    def __init__(self, data=list(), source=''):
        self.data = data
        self.host = db_info.HOST
        self.database = db_info.DATABASE
        self.user = db_info.USER
        self.password = db_info.PASSWORD
        self.source = source
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

        sql_values = set()
        for row in self.data:
            if isinstance(row, dict):
                sql_statement = '''
                                INSERT INTO 
                                            positions(position_id,
                                            url,
                                            title,
                                            description,
                                            key_words,
                                            source_name,
                                            category,
                                            salary,
                                            date_registered,
                                            type_of_work,
                                            experience,
                                            employment_type,
                                            operating_mode,
                                            company_name
                                            ) 
                    VALUES(default, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE , %s,%s,%s,%s,%s)
                    ON CONFLICT (url) DO UPDATE SET date_registered = CURRENT_DATE;
                    '''
                try:
                    sql_values = (row['url'],
                                  row['title'],
                                  row['description'],
                                  row['key_words'],
                                  row['source_name'],
                                  row['category'],
                                  row['salary'],
                                  row['type_of_work'],
                                  row['experience'],
                                  row['employment_type'],
                                  row['operating_mode'],
                                  row['company_name']
                                  )
                except KeyError as e:
                    with open(f'files\\error_rows_{self.source}.txt', 'a+', encoding='utf-8') as file:
                        file.write(str(row) + '\n')
                        logger.critical('KeyError: Missing key in data dictionary')
                        logger.exception(f'Exception : {e}')
                    continue
                except Exception as e:
                    with open(f'files\\error_rows_{self.source}.txt', 'a+', encoding='utf-8') as file:
                        file.write(str(row) + '\n')
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

    def read(self, statement, columns=list()):
        self.connect()
        self.cur.execute(statement)
        if len(columns) != 0:
            df = pd.DataFrame(self.cur.fetchall(), columns=columns)
        else:
            df = pd.DataFrame(self.cur.fetchall())
            col_names = {idx: desc[0] for idx, desc in enumerate(self.cur.description)}
            df.rename(columns=col_names, inplace=True)
        self.disconnect()
        return df

    def csv_download(self):
        from datetime import date
        import openpyxl
        # download data from v_positions gold
        df = self.read('''SELECT ass.value, pos.* 
                          FROM v_positions_gold pos
                          LEFT OUTER JOIN ASSESSED_IDS ass ON pos.position_id=ass.position_id''')
        df.to_csv(f"files\data{date.today().strftime('%y_%m_%d')}.csv", index=False)


    def populate_assessed_ids(self, csv_name):
        self.connect()

        create_temp_table = '''
                            CREATE TEMP TABLE IF NOT EXISTS temp_assessed_ids (
                            value NUMERIC, position_id NUMERIC, company_id NUMERIC, 
                            title TEXT, description TEXT, key_words TEXT,
                            k_words_desc TEXT, url TEXT, source_name TEXT, 
                            category TEXT, salary TEXT, date_registered TEXT,
                            type_of_work TEXT, experience TEXT, employment_type TEXT, 
                            operating_mode TEXT, company_name TEXT
                            )
                            '''

        copy_statement = f'''COPY temp_assessed_ids FROM 'C:/Users/48575/PycharmProjects/JSE4/files/{csv_name}.csv'
                            DELIMITER ','  CSV HEADER; '''

        insert_statement = '''INSERT INTO assessed_ids (value, position_id)
                                SELECT value, position_id
                                FROM temp_assessed_ids
                                ON CONFLICT (position_id)
                                DO UPDATE SET value = EXCLUDED.value;
                              '''
        try:
            self.cur.execute(create_temp_table)
            self.cur.execute(copy_statement)
            self.cur.execute(insert_statement)
            self.conn.commit()
        except Exception as e:
            logger.info('could not populate table assessed_ids')
            logger.exception(f'exception: {e}')

    def data_adjust(self):
        self.connect()

        sql_statement = '''
            call public.latest_data_raw_bronze_to_silver()
        '''

        sql_statement2 = '''
            call public.p_update_comp_ids_in_positions_silver()
        '''

        sql_collect_key_desc = '''
            call p_collect_key_words()
        '''

        sql_select_unattractive_pos_ids = '''
            call p_populate_un_attractive_positions() 
        '''
        try:
            self.cur.execute(sql_collect_key_desc)
            self.cur.execute(sql_statement)
            self.cur.execute(sql_statement2)
            self.cur.execute(sql_select_unattractive_pos_ids)

            self.conn.commit()
        except Exception as e:
            print(f"Error: {e}")
            self.conn.rollback()
        finally:
            self.disconnect()
