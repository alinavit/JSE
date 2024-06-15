import requests
import database
import logging.config
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from bs4 import BeautifulSoup

import config

logging.config.fileConfig('conf/logging.conf')
logger = logging.getLogger('DataProcessing')


class DataProcessing:
    def __init__(self, url_list, selenium=False, main_url='', source_name='na', cookies_selector=None):
        self.url_list = url_list
        self.selenium = selenium
        self.main_url = main_url
        self.source_name = source_name
        self.cookies_selector = cookies_selector

        self.soup = list()

    def cookies_accept(self, driver):
        if self.cookies_selector:
            accept_cookies = driver.find_element(By.CSS_SELECTOR, self.cookies_selector)
            accept_cookies.click()
            time.sleep(3)

    def extract_selenium(self, link=None):
        # main page read
        if link is None:
            for url in self.url_list:
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
                driver.get(url)
                time.sleep(3)
                self.cookies_accept(driver=driver)
                page_source = driver.page_source
                self.soup.append(BeautifulSoup(page_source, 'lxml'))
                driver.quit()
        # offer read
        else:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            driver.get(link)
            time.sleep(3)
            self.cookies_accept(driver=driver)
            page_source = driver.page_source
            soup_main = BeautifulSoup(page_source, 'lxml')
            driver.quit()
            return soup_main

    def extract_requests(self):
        for url in self.url_list:
            try:
                web_page = requests.get(url).text
                self.soup.append(BeautifulSoup(web_page, 'lxml'))

                logging.info(f'Data fetched from {url}')
            except Exception as e:
                logging.critical(f'Error occurred fetching data from {url}')
                logging.exception(f'Exception: {e}')

    def transform(self):
        pass

    def run(self):
        if self.selenium:
            self.extract_selenium()
        else:
            self.extract_requests()

        data = self.transform()

        database.JSEDatabase(data=data, source=self.source_name).write()


class DataProcessingJJI(DataProcessing):
    def __init__(self, url_list, selenium=False, main_url='', source_name='na'):
        super().__init__(url_list, selenium, main_url, source_name)

        self.soup = list()

    def transform(self):
        data = []
        for url, page in zip(self.url_list, self.soup):

            jobs_list = page.find_all('div', class_='css-2crog7')
            if len(jobs_list) == 0:
                logging.warning('jobs_list variable is empty. Check if anything changed in the source')

            for job in jobs_list:
                row = dict()

                row['url'] = ''
                row['title'] = ''
                row['salary'] = ''
                row['company_name'] = ''
                try:
                    row['url'] = self.main_url + job.a['href']
                    row['title'] = job.find('div', class_='MuiBox-root css-6vg4fr').h2.text
                    row['salary'] = job.find('div', class_='css-17pspck').text
                    # offer_date = job.find('div', class_='css-1wv2lui').text
                    row['company_name'] = job.find('div', class_='css-aryx9u').text
                except Exception as e:
                    logging.critical('Data could not be fetched')
                    logging.exception(f'Exception: {e}')

                row['type_of_work'] = ''
                row['experience'] = ''
                row['employment_type'] = ''
                row['operating_mode'] = ''
                row['key_words'] = ''
                row['description'] = ''
                try:
                    job_details = requests.get(row['url']).text
                    details_soup = BeautifulSoup(job_details, 'lxml')

                    # Details from job offer load
                    attr = details_soup.find_all('div', class_='css-6q28fo')
                    attr_list = []
                    for i in attr:
                        attr_list.append(i.text)
                    row['type_of_work'] = attr_list[0]
                    row['experience'] = attr_list[1]
                    row['employment_type'] = attr_list[2]
                    row['operating_mode'] = attr_list[3]

                    key_words = details_soup.find_all('div', class_='css-cjymd2')
                    key_words_list = []
                    for i in key_words:
                        key_words_list.append(i.text)
                    row['key_words'] = key_words_list

                    # FULL DESCRIPTION
                    description = details_soup.find_all('div', class_='css-6sm4q6')
                    description_text = ''
                    for i in description:
                        description_text = description_text + i.text + ' '
                    row['description'] = description_text
                except Exception as e:
                    logging.critical('Error occurred fetching job details')
                    logging.exception(f'Exception: {e}')

                row['source_name'] = self.source_name
                row['category'] = url

                data.append(row)
                logging.info(f'Successfully fetched for: {row["title"]}')

        return data


class DataProcessingST(DataProcessing):
    def __init__(self, url_list, selenium=False, main_url='', source_name='na', cookies_selector=None):
        super().__init__(url_list, selenium, main_url, source_name, cookies_selector)

        self.soup = list()

    def transform(self):
        data = []

        # PARSE GENERAL PAGE FOR IMPORTANT INFORMATION
        for url, page in zip(self.url_list, self.soup):
            soup_offer = None

            for i in page.find_all('div', class_='res-urswt'):
                row = config.ROW.copy()
                try:
                    row['title'] = i.h2.text
                    row['url'] = self.main_url + i.h2.a['href']
                    row['company_name'] = i.find('span', class_='res-btchsq').text
                    op_mode = i.find('span', class_='res-1qh7elo').text

                    if i.find('span', attrs={'data-at': 'job-item-work-from-home'}) is not None:
                        op_mode2 = i.find('span', attrs={'data-at': 'job-item-work-from-home'}).text
                        row['operating_mode'] = op_mode + ' ' + op_mode2

                        # PARSE DIRECT JOB PAGE FOR INFORMATION
                        soup_offer = self.extract_selenium(link=row['url'])

                except Exception as e:
                    logging.critical(f'Error extracting {url} using selenium')
                    logging.exception(f'Exception: {e}')

                try:
                    if soup_offer:
                        # employment_type_st
                        for emp_type in soup_offer.find_all('li',
                                                            class_='job-ad-display-ve6qfw '
                                                                   'at-listing__list-icons_contract-type'):
                            if emp_type:
                                row['employment_type'] = emp_type.find('span', class_='job-ad-display-1whr5zf').text

                        # description
                        for desc in soup_offer.find_all('div', attrs={'data-at': 'job-ad-content'}):
                            row['description'] = desc.text
                except Exception as e:
                    logging.critical(f'Error occurred extracting details')
                    logging.exception(f'Exception: {e}')

                row['source_name'] = self.source_name
                row['category'] = url

                data.append(row)

        return data
