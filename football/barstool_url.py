import time
from os import environ
from configparser import ConfigParser
from datetime import datetime
from random import randrange

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utilities.logging import get_logger
from utilities.utils import get_driver, str_to_timedelta, add_url_redis, actions_on_page

# read config file
config_parser = ConfigParser()
config_parser.read('conf/barstool.conf')
module_conf = config_parser["MODULE"]

# init logging
logger_name = environ.get('football_barstool_url_get_logger', 'football_barstool_url_logger')
# for local logs storage and stdout use DEBUG_FLAG = 1
DEBUG_FLAG = environ.get('football_barstool_url_DEBUG_FLAG', 0)
log_level = environ.get('football_barstool_url_log_level', 'WARNING')

logger = get_logger(logger_name, DEBUG_FLAG, log_level)

# other variables
URL = environ.get('football_barstool_url', module_conf.get('URL'))
module_work_duration = str_to_timedelta(environ.get('football_barstool_url_module_work_duration', module_conf.get('module_work_duration')))
update_frequency = str_to_timedelta(environ.get('football_barstool_url_update_frequency', module_conf.get('update_frequency')))
browser = environ.get('football_barstool_url_browser', module_conf.get('browser_url'))

scrap_step = int(environ.get('football_scrap_step', module_conf.get('scrap_step')))
scrap_limit = int(environ.get('football_scrap_limit', module_conf.get('scrap_limit')))

# init web driver
driver = get_driver(browser)
driver.get(URL)

logger.warning(f'Module started working with parameters:\nURL: {URL}\nmodule_work_duration: {module_work_duration}\nupdate_frequency: {update_frequency}\nbrowser: {browser}\nlogger_name: {logger_name}\nlog_level: {log_level}\nDEBUG_FLAG: {DEBUG_FLAG}')


def get_max_str(lst):
    max_str = lst[0]   # list is not empty
    for x in lst:
        if len(x) > len(max_str):
            max_str = x
    return max_str

def check_capture():
    while True:
        try:
            driver.find_element(By.XPATH, '//h2[contains(text(), "Confirm Your Responsible Gaming Settings")]').text
            logger.error('Confirm Your Responsible Gaming Settings')
            n_btn = driver.find_element(By.XPATH, ".//button[@aria-label='Not Now']")
            n_btn.click()
            time.sleep(3)
            continue
        except:
            break


def main():
    module_operate_until = datetime.now() + module_work_duration
    failure_count = 0
    count_scraps = 0

    while datetime.now() < module_operate_until:
        parsing_start_time = time.time()
        urls_list = []
        try:
            logger.warning(f'Start scraping urls')
            games_present = 0

            check_capture()

            try:
                WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Football')]"))).click()
            except:
                logger.warning("No football games")

            for ft_game in driver.find_elements(By.XPATH, "//div[@class='flex w-full justify-between']"):
                if ('LIVE' in ft_game.text 
                    and ('NFL' in ft_game.text or 'NCAAF' in ft_game.text)):
                    games_present = 1
                    ft_game.click()
                    time.sleep(5)
                try:
                    # active_page = driver.find_element(By.XPATH, "//div[@data-testid='marketplace-shelf-']")
                    active_page = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//div[@data-testid='marketplace-shelf-']")))
                except:
                    time.sleep(10)
                    continue
                
                match_rows = active_page.find_elements(By.XPATH, ".//div[contains(@class, 'bg-card-primary rounded p-4')]")

                for i in range(len(match_rows)):
                    active_page = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//div[@data-testid='marketplace-shelf-']")))
                    match_rows = active_page.find_elements(By.XPATH, ".//div[contains(@class, 'bg-card-primary rounded p-4')]")
                    participants_card = match_rows[i]

                    l_card = participants_card.find_element(By.XPATH, ".//button[@data-testid='navigate-to-matchup-btn']")
                    l_card_data = participants_card.text.split("\n")[0]
                    if 'LIVE' in l_card_data:
                        g_btn = participants_card.find_element(By.XPATH, ".//button[@data-testid='team-name']")
                        g_btn.click()
                        urls_list.append(driver.current_url)
                    else:
                        continue

                    driver.back()

                logger.info(f"Found {len(urls_list)} url's")
            
            # save data to redis db
            for rd_url in urls_list:
                stream_name = rd_url.split('/')[-1].split('?')[0]
                saving_result = add_url_redis(rd_url, 'barstool', f'football_barstool_prop_{stream_name}')
                logger.info(f'Result: {saving_result}')                
            count_scraps += 1

            if games_present == 0:
                logger.warning('There are no live games, waiting for some time and trying again')
                time.sleep(randrange(4000, 12000, 10) / 1000)
                driver.refresh()

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
            if count_scraps == scrap_limit:
                driver.refresh()                
                count_scraps = 0

        parsing_work_time = time.time() - parsing_start_time
        time.sleep(max(0.01, update_frequency.total_seconds() - parsing_work_time))

    driver.quit()
    logger.warning('Script successfully ended working at the set time')


if __name__ == "__main__":
    main()
