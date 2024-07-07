import requests
import database
import logging
import logging.config
import time
import json

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from bs4 import BeautifulSoup

import config2

logging.config.fileConfig("C:\\Users\\48575\\PycharmProjects\\JSE4\\conf\\logging.conf")
logger = logging.getLogger('dataProcessing')
logger.info('Data Processing')


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
                options = Options()
                options.add_argument('--headless')
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                driver.get(url)
                time.sleep(3)
                self.cookies_accept(driver=driver)
                page_source = driver.page_source
                self.soup.append(BeautifulSoup(page_source, 'lxml'))
                driver.quit()
        # offer read
        else:
            options = Options()
            options.add_argument('--headless')
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
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

                logger.info(f'Data fetched from {url}')
            except Exception as e:
                logger.critical(f'Error occurred fetching data from {url}')
                logger.exception(f'Exception: {e}')

    def transform(self):
        pass

    def run(self):
        if self.selenium:
            self.extract_selenium()
        else:
            self.extract_requests()

        self.transform()


class DataProcessingJJI(DataProcessing):
    def __init__(self, url_list, selenium=False, main_url='', source_name='na'):
        super().__init__(url_list, selenium, main_url, source_name)

        self.soup = list()

    def transform(self):
        data = []
        logging.info('Test transform')
        for url, page in zip(self.url_list, self.soup):

            jobs_list = page.find_all('div', attrs={'item': '[object Object]'})
            if len(jobs_list) == 0:
                logger.warning('Cannot fetch data from source. Check if anything changed in the source')

            for job in jobs_list:
                row = config2.ROW.copy()

                try:
                    row['url'] = self.main_url + job.a['href']
                except Exception as e:
                    logger.critical('url could not be fetched')
                    logger.exception(f'Exception: {e}')

                try:
                    time.sleep(3)
                    job_details = requests.get(row['url']).text
                    details_soup = BeautifulSoup(job_details, 'lxml')

                    details_in_txt = details_soup.find('script', attrs={'id': '__NEXT_DATA__'}).text
                    details_in_json = json.loads(details_in_txt)

                    row['title'] = details_in_json['props']['pageProps']['offer']['title']
                    row['company_name'] = details_in_json['props']['pageProps']['offer']['companyName']
                    row['operating_mode'] = details_in_json['props']['pageProps']['offer']['workplaceType']['value']
                    row['employment_type'] = ','.join([str(i['type']) for i in details_in_json['props']['pageProps']['offer']['employmentTypes']])
                    row['description'] = BeautifulSoup(details_in_json['props']['pageProps']['offer']['body'], 'lxml').text

                    for emp_type in details_in_json['props']['pageProps']['offer']['employmentTypes']:
                        sal_from = emp_type['fromPln']
                        if sal_from is None:
                            sal_from = ''
                        elif isinstance(sal_from, int):
                            sal_from = str(sal_from)

                        sal_to = emp_type['toPln']
                        if sal_to is None:
                            sal_to = ''
                        elif isinstance(sal_to, int):
                            sal_to = str(sal_to)
                        sal = sal_from + ' - ' + sal_to

                        row['salary'] = row['salary'] + sal

                    row['type_of_work'] = details_in_json['props']['pageProps']['offer']['workingTime']['label']
                    row['experience'] = details_in_json['props']['pageProps']['offer']['experienceLevel']['value']
                    row['key_words'] = [str(skill['name'] )for skill in details_in_json['props']['pageProps']['offer']['requiredSkills']]
                    row['source_name'] = self.source_name
                    row['category'] = details_in_json['props']['pageProps']['offer']['category']['name']

                except Exception as e:
                    logger.critical(f"job details for {row['url']} not detected")
                    logger.exception(f'Exception: {e}')

                data.append(row)
                logger.info(f'Successfully fetched for: {row["title"]}')

                if len(data) == 1:
                    database.JSEDatabase(data=data, source=self.source_name).write()
                    data = []


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
                row = config2.ROW.copy()
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
                    logger.critical(f'Error extracting {url} using selenium')
                    logger.exception(f'Exception: {e}')

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
                    logger.critical(f'Error occurred extracting details')
                    logger.exception(f'Exception: {e}')

                row['source_name'] = self.source_name
                row['category'] = url

                logger.info(f"Fetched data for {row['title']}")
                data.append(row)

                if len(data) == 1:
                    database.JSEDatabase(data=data, source=self.source_name).write()
                    data = []


class DataProcessingNFJ(DataProcessing):
    def __init__(self, url_list, selenium=False, main_url='', source_name='na', cookies_selector=None):
        super().__init__(url_list, selenium, main_url, source_name, cookies_selector)

        self.soup = list()

    def transform(self):
        data = []
        for url, page in zip(self.url_list, self.soup):
            page_deeper = page.find_all('div', class_='list-container ng-star-inserted')
            for part in page_deeper:
                for jsection in part.find_all('a'):
                    row = config2.ROW.copy()

                    row['url'] = self.main_url + jsection['href']

                    time.sleep(2)

                    req = requests.get(row['url']).text
                    soup_details = BeautifulSoup(req, 'lxml')

                    data_as_txt = soup_details.find('script', attrs={'id': 'serverApp-state'}).text
                    data_as_json = json.loads(data_as_txt)

                    key = ''

                    for k in data_as_json.keys():
                        if not isinstance(data_as_json[k], dict):
                            continue
                        elif 'b' not in list(data_as_json[k].keys()):
                            continue
                        elif not isinstance(data_as_json[k]['b'], dict):
                            continue
                        elif 'title' not in data_as_json[k]['b'].keys():
                            continue
                        else:
                            key = k

                    try:
                        row['title'] = data_as_json[key]['b']['title']
                    except Exception as e:
                        logger.warning(f'Problem fetching title: {e} ')

                    try:
                        row['company_name'] = data_as_json[key]['b']['company']['name']
                    except Exception as e:
                        logger.warning(f'Problem fetching company name: {e} ')
                    try:
                        row['operating_mode'] = data_as_json[key]['b']['location']['places'][0]['city']
                    except Exception as e:
                        logger.warning(f'Problem fetching operating mode {e} ')
                    try:
                        row['employment_type'] = list(data_as_json[key]['b']['essentials']['originalSalary']['types'].keys())
                    except Exception as e:
                        logger.warning(f'Problem fetching employment type: {e} ')

                    descript_tasks = ''
                    descript_desc = ''
                    try:
                        descript_tasks = str(data_as_json[key]['b']['specs']['dailyTasks'])
                    except Exception as e:
                        logger.warning(f'Problem fetching description (tasks): {e} ')

                    try:
                        descript_desc = str(BeautifulSoup(data_as_json[key]['b']['requirements']['description'], 'lxml').text)
                    except Exception as e:
                        logger.warning(f'Problem fetching description (desc): {e} ')

                    row['description'] = descript_tasks + descript_desc

                    try:
                        row['salary'] = [val['range'] for key, val in data_as_json[key]['b']['essentials']['originalSalary']['types'].items()]
                    except Exception as e:
                        logger.warning(f'Problem fetching salary: {e} ')
                    try:
                        row['experience'] = data_as_json[key]['b']['basics']['seniority']
                    except Exception as e:
                        logger.warning(f'Problem fetching experience: {e} ')
                    try:
                        row['key_words'] = [skill['value'] for skill in data_as_json[key]['b']['requirements']['musts']]
                    except Exception as e:
                        logger.warning(f'Problem fetching key words: {e} ')

                    row['source_name' ]= self.source_name

                    try:
                        row['category'] = data_as_json[key]['b']['basics']['category']
                    except Exception as e:
                        logger.warning(f'Problem fetching category: {e} ')
                    try:
                        tp_work_txt = soup_details.find('script', attrs={'type': 'application/ld+json'}).text
                        tp_work_json = json.loads(tp_work_txt)
                        row['type_of_work'] = tp_work_json['@graph'][2]['jobLocationType']
                    except Exception as e:
                        logger.warning(f'Problem fetching type of work: {e} ')

                    logger.info(f'Successfully fetched data for {row["title"]}')
                    data.append(row)
                    if len(data) == 1:
                        database.JSEDatabase(data=data, source=self.source_name).write()
                        data = []


class DataProcessingPR(DataProcessing):
    def __init__(self, url_list, selenium=False, main_url='', source_name='na', cookies_selector=None):
        super().__init__(url_list, selenium, main_url, source_name, cookies_selector)

        self.soup = list()

    def transform(self):
        import json
        data = []
        for cat_link in self.url_list:

            web = requests.get(cat_link).text
            soup = BeautifulSoup(web, 'lxml')

            info_doc = soup.find('script', attrs={'id': '__NEXT_DATA__'}).text
            json_data = json.loads(info_doc)

            props = json_data['props']['pageProps']['data']
            jobs = props['jobOffers']['groupedOffers']

            logger.info(f'Fetched data from {cat_link}')

            for job_unit in jobs:
                row = config2.ROW.copy()

                row['title'] = job_unit['jobTitle']
                row['url'] = job_unit['offers'][0]['offerAbsoluteUri']
                row['key_words'] = job_unit['technologies']
                row['company_name'] = job_unit['companyName']
                row['salary'] = job_unit['salaryDisplayText']
                row['experience'] = job_unit['positionLevels']
                row['employment_type'] = job_unit['typesOfContract']
                row['operating_mode'] = str(job_unit['workModes'])
                row['employment_type'] = job_unit['workSchedules']

                time.sleep(2)
                r = requests.get(row['url']).text
                soup = BeautifulSoup(r, from_encoding='utf-8')


                desc1 = ''
                desc2 = ''
                desc3 = ''

                try:
                    desc1 = soup.find('div', attrs={'data-scroll-id': 'responsibilities-1'}).text
                except Exception as e:
                    logger.warning(f'Description has been not extracted. Details: {e}')
                    pass
                try:
                    desc2 = soup.find('div', attrs={'data-scroll-id': 'requirements-1'}).text
                except Exception as e:
                    logger.warning(f'Description has been not extracted. Details: {e}')
                    pass
                try:
                    desc3 = soup.find('div', attrs={'data-scroll-id': 'offered-1'}).text
                except Exception as e:
                    logger.warning(f'Description has been not extracted. Details: {e}')
                    pass

                row['description'] = desc1 + ' ' + desc2 + ' ' + desc3

                data.append(row)

        return data


class DataProcessingIND(DataProcessing):
    def __init__(self, url_list, selenium=False, main_url='', source_name='na', cookies_selector=None):
        super().__init__(url_list, selenium, main_url, source_name, cookies_selector)

        self.soup = list()

    def transform(self):
        data = []
        for url, page in zip(self.url_list, self.soup):
            page_detail = page.find_all('div', class_='job_seen_beacon')

            row = config2.ROW.copy()

            logger.info(f'Data fetched for {url}')

            for offer in page_detail:
                row['title'] = offer.find('h2').text
                row['url'] = self.main_url + offer.find('h2').a['href']
                row['company_name'] = offer.find('span', attrs={'data-testid': 'company-name'}).text
                # row['type_of_work'] = offer.find('div', attrs={'data-testid': 'text-location'}).text

                # offer OPEN
                offer_soup = self.extract_selenium()
                try:
                    row['type_of_work'] = offer_soup.find(
                        'div',
                        attrs={'data-testid': 'jobsearch-OtherJobDetailsContainer'}).text

                except Exception as e:
                    logger.warning(f'Type of work has not been extracted. Details: {e}')

                try:
                    row['description'] = offer_soup.find('div', attrs={'id': 'jobDescriptionText'}).text
                except Exception as e:
                    logger.warning(f'Description has not been extracted. Details: {e}')

                if 'junior' in row['title'] or 'junior' in row['description'].lower():
                    row['experience'] = 'junior'
                elif 'senior' in row['title'] or 'senior' in row['description'].lower():
                    row['experience'] = 'senior'
                else:
                    row['experience'] = 'middle'

                data.append(row)

        return data
