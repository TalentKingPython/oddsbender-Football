from os import environ
import time
from configparser import ConfigParser
from datetime import datetime
from random import randrange

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from utilities.logging import get_logger
from utilities.utils import get_driver, str_to_timedelta, add_url_redis, actions_on_page


# read config file
config_parser = ConfigParser()
config_parser.read('conf/sugarhouse.conf')
module_conf = config_parser["MODULE"]

# init logging
logger_name = environ.get('football_sugarhouse_url_get_logger', 'football_sugarhouse_url_logger')
# for local logs storage and stdout use DEBUG_FLAG = 1
DEBUG_FLAG = environ.get('football_sugarhouse_url_DEBUG_FLAG', 0)
log_level = environ.get('football_sugarhouse_url_log_level', 'WARNING')

logger = get_logger(logger_name, DEBUG_FLAG, log_level)

# other variables
URL = environ.get('football_sugarhouse_url', module_conf.get('URL'))
module_work_duration = str_to_timedelta(environ.get('football_sugarhouse_url_module_work_duration', module_conf.get('module_work_duration')))
update_frequency = str_to_timedelta(environ.get('football_sugarhouse_url_update_frequency', module_conf.get('update_frequency')))
browser = environ.get('football_sugarhouse_url_browser', module_conf.get('browser_url'))

scrap_step = int(environ.get('football_scrap_step', module_conf.get('scrap_step')))
scrap_limit = int(environ.get('football_scrap_limit', module_conf.get('scrap_limit')))

# init web driver
driver = get_driver(browser)
driver.get(URL)

logger.warning(f'Module started working with parameters:\nURL: {URL}\nmodule_work_duration: {module_work_duration}\nupdate_frequency: {update_frequency}\nbrowser: {browser}\nlogger_name: {logger_name}\nlog_level: {log_level}\nDEBUG_FLAG: {DEBUG_FLAG}')

def section_expanded(bt_id, driver_):
    try:
        hidden_tab = driver_.find_element(By.XPATH, f"//button[@id='{bt_id}']")
        hidden_tab.click()
        time.sleep(5)
        logger.info(f'Opened {hidden_tab.text}')
        return True
    except:
        return False

def main():
    module_operate_until = datetime.now() + module_work_duration

    failure_count = 0
    count_scraps = 0

    while datetime.now() < module_operate_until:
        parsing_start_time = time.time()
        try:
            logger.info(f'Start scraping urls')

            # open NFL
            btn_ids = [
                'accordion-NFL',
                'accordion-NFL Preseason',
                'accordion-NCAAF',
                'accordion-NCAAF FCS'
            ]
            
            for b_id in btn_ids:
                all_games = driver.find_elements(By.XPATH, f"//div[@aria-labelledby='{b_id}']")
                # click the game section if the tab was hidden
                if len(all_games) == 0:
                    if section_expanded(b_id, driver):
                        all_games = driver.find_elements(By.XPATH, f"//div[@aria-labelledby='{b_id}']") 
                    else:
                        continue

                urls_list = all_games[0].find_elements(By.XPATH, ".//article[contains(@data-testid, 'listview-group-')]")

                logger.info(f"Found {len(urls_list)} url's")

                # save data to redis db
                for rd_url in urls_list:
                    stream_name = rd_url.get_attribute("data-testid").split('-')[-1]
                    r_url = f'https://pa.playsugarhouse.com/?page=sportsbook&l=RiversPhiladelphia#event/live/{stream_name}'
                    saving_result = add_url_redis(r_url, 'sugarhouse', f'football_sugarhouse_prop_{stream_name}')
                    logger.info(f'Result: {saving_result}')      
                    #           
                count_scraps += 1

                # reset unsuccessful attempts in main loop
                failure_count = 0

                if len(urls_list) == 0:
                    logger.warning('There are no live games, waiting for some time and trying again')
                    time.sleep(randrange(4000, 12000, 10) / 1000)
                    driver.refresh()
                    continue

        except KeyboardInterrupt:
            logger.info("Keyboard Interrupt. Quit the driver!")
            driver.quit()
            logger.warning(f'Module stopped working')
            break

        except Exception as e:
            logger.exception(f'Stop script with errors:\n{e}')
            failure_count += 1
            if failure_count >= 5:
                driver.quit()
                logger.exception(f'Script exited after {failure_count} unsuccessful attempts to start the main loop')
                break
            
        if count_scraps % scrap_step == 0:
            actions_on_page(driver=driver, class_name="sc-fzXfNO gPURds")
            if count_scraps == scrap_limit:
                driver.refresh()                
                count_scraps = 0

        parsing_work_time = time.time() - parsing_start_time
        time.sleep(max(0, update_frequency.total_seconds() - parsing_work_time))

    driver.quit()
    logger.warning('Script successfully ended working at the set time')


if __name__ == "__main__":
    main()
