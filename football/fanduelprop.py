import time
from configparser import ConfigParser
from datetime import datetime
from os import environ

from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utilities.logging import get_logger
from utilities.utils import str_to_timedelta, split_string, get_driver, add_data_redis, update_redis_status, actions_on_page, text_filter, read_url_redis
from utilities.driver_proxy import get_driver_proxy


# read config file
config_parser = ConfigParser()
config_parser.read('conf/fanduel.conf')
module_conf = config_parser["MODULE"]

# init logging
logger_name = environ.get('football_fanduelprop_get_logger', 'football_fanduel_prop')
# for local logs storage and stdout use DEBUG_FLAG = 1
DEBUG_FLAG = environ.get('PROP_LOG_DEBUG_FLAG', 0)
log_level = environ.get('football_fanduelprop_log_level', 'WARNING')

logger = get_logger(logger_name, DEBUG_FLAG, log_level)

# other variables
# URL = environ['fanduel_prop_url']
URL = None
file_tail = None

module_work_duration = str_to_timedelta(environ.get('football_fanduelprop_module_work_duration', module_conf.get('module_work_duration')))
update_frequency = str_to_timedelta(environ.get('football_fanduelprop_update_frequency', module_conf.get('update_frequency')))
browser = environ.get('football_fanduelprop_browser', module_conf.get('browser_prop'))

scrap_step = int(environ.get('football_scrap_step', module_conf.get('scrap_step')))
scrap_limit = int(environ.get('football_scrap_limit', module_conf.get('scrap_limit')))

# init web driver
# driver = get_driver(browser)
# driver.get(URL)
driver = None

logger.warning(f'Module started working with parameters:\nURL: {URL}\nmodule_work_duration: {module_work_duration}\nupdate_frequency: {update_frequency}\nbrowser: {browser}\nlogger_name: {logger_name}\nlog_level: {log_level}\nDEBUG_FLAG: {DEBUG_FLAG}')


def check_capture():
    global driver
    while True:
        try:
            driver, ip_list = get_driver_proxy()
            driver.get(URL)
            driver.find_element(By.XPATH, '//h1[contains(text(), "Please verify you are a human")]').text
            logger.error('Please verify you are a human')
            time.sleep(3)
            driver.quit()
            save_blocked_proxies([ip_list])
            continue
        except:
            break

def save_blocked_proxies(b_ip):
    import os
    BASE_DIR = (os.path.dirname(os.path.abspath(__file__)))
    with open(f'{BASE_DIR}/utilities/blocked_ips.txt', 'a') as f:
        f.write('\n'.join(b_ip))

def click_on_web_element(element: WebElement):
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
    driver.execute_script("arguments[0].click();", element)


def open_bet_list(all_bets_on_page: list):
    logger.info(f'Open all bets on the page')
    g_sections = all_bets_on_page.find_elements(By.XPATH, './/li')
    for ind, single_bet_table in enumerate(g_sections):
        if ind == 0:
            continue
        try:
            single_bet_table.click()
        except StaleElementReferenceException:
            logger.warning(f'Bet table element has changed the reference. Unable to open bet')
            continue
      

def parse_prop_bets(bet_table, additional_param, title):
    prop_bet_list = []

    try:
        is_timeout = 0 if ':' in additional_param.get('game_time') else 1
    except:
        is_timeout = 1
    
    gt_data = additional_param.get('game_time')

    if 'Total' in bet_table[0]:
        try:
            bet_name = bet_table[0].split(' ')[0] + ' Quarter Total Points'
            bet_type = [bet_table[4], bet_table[6]]
            odds = [bet_table[5], bet_table[7]]
            for i in range(2):
                prop_bet_dict = {
                    'SPORT': additional_param.get('sport'),
                    'GAME_TYPE': additional_param.get('game_type'),
                    'IS_PROP': 1,
                    'GAME_NAME': additional_param.get("game_name"),
                    'BET_NAME': bet_name,
                    'BET_TYPE': bet_type[i],
                    'ODDS': odds[i],
                    'HOME_TEAM': additional_param.get('home_team'),
                    'AWAY_TEAM': additional_param.get('away_team'),
                    'ALIGNED_BET_NAME': bet_name.replace(additional_param.get('home_team'), 'Home Team').replace(additional_param.get('away_team'), 'Away Team').replace('Under', 'U').replace('Over', 'O'),
                    'ALIGNED_BET_TYPE': bet_type[i].replace(additional_param.get('home_team'), 'Home Team').replace(additional_param.get('away_team'), 'Away Team').replace('Under', 'U').replace('Over', 'O'),
                    'PERIOD_TYPE': 'Quarter',
                    'PERIOD_VALUE': gt_data.split('-')[0].strip(),
                    'PERIOD_TIME': gt_data.split('-')[1].strip(),
                    'IS_TIMEOUT': is_timeout,
                    'SPORTS_BOOK': 'Fanduel',
                    'TIMESTAMP': additional_param.get('time_stamp'),
                    'URL': URL
                }
                prop_bet_list.append(prop_bet_dict)
        except:
            pass
    
    elif 'Spread' in bet_table[0]:
        pass
    else:
        try:
            bet_name = bet_table[0].split(' ')[0] + ' Quarter Moneyline'
            bet_type = [bet_table[1], bet_table[5]]
            odds = [bet_table[2], bet_table[6]]
            for i in range(2):
                prop_bet_dict = {
                    'SPORT': additional_param.get('sport'),
                    'GAME_TYPE': additional_param.get('game_type'),
                    'IS_PROP': 1,
                    'GAME_NAME': additional_param.get("game_name"),
                    'BET_NAME': bet_name,
                    'BET_TYPE': f'{bet_type[i]} { odds[i]}',
                    'ODDS': odds[i],
                    'HOME_TEAM': additional_param.get('home_team'),
                    'AWAY_TEAM': additional_param.get('away_team'),
                    'ALIGNED_BET_NAME': bet_name.replace(additional_param.get('home_team'), 'Home Team').replace(additional_param.get('away_team'), 'Away Team').replace('Under', 'U').replace('Over', 'O'),
                    'ALIGNED_BET_TYPE': bet_type[i].replace(additional_param.get('home_team'), 'Home Team').replace(additional_param.get('away_team'), 'Away Team').replace('Under', 'U').replace('Over', 'O') + ' ' + odds[i],
                    'PERIOD_TYPE': 'Quarter',
                    'PERIOD_VALUE': gt_data.split('-')[0].strip(),
                    'PERIOD_TIME': gt_data.split('-')[1].strip(),
                    'IS_TIMEOUT': is_timeout,
                    'SPORTS_BOOK': 'Fanduel',
                    'TIMESTAMP': additional_param.get('time_stamp'),
                    'URL': URL
                }
                prop_bet_list.append(prop_bet_dict)
        except:
            pass
    
    logger.info(f'Bet {bet_name} scraped successfully')
    return prop_bet_list

def main():
    module_operate_until = datetime.now() + module_work_duration
    exception_counter = 0
    count_scraps = 0

    global URL, driver

    while datetime.now() < module_operate_until:

        urls = read_url_redis('fanduel')

        for redis_url in urls:

            try:
                driver.quit()
            except:
                pass
            
            URL = redis_url[1]
            file_tail = URL.split('/')[-1]

            check_capture()

            logger.info('Start scraping Fanduel props')
            previous_bet_bur_buttons = driver.find_elements(By.XPATH, '//div[@style="height: 100%;"]//a')
            additional_param = {}

            # get type of sport
            try:
                additional_param['sport'] = URL.split('/')[3].capitalize()
            except:
                additional_param['sport'] = 'Not identified'
                logger.warning('It’s impossible to identify game type')

            # check if the game_type field is active
            try:
                game_online = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'LiveTag_svg__a')))
                if game_online:
                    additional_param['game_type'] = 'Live'
                if not game_online:
                    additional_param['game_type'] = 'Pre-game'
            except:
                additional_param['game_type'] = 'Unable to Get'
                logger.warning('There are no live game element found')

            # get game_time
            try:
                additional_param['game_time'] = WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.XPATH, "//span[contains(@class, '') and contains(text(),':') and not(contains(text(),'/'))]"))).text
            except:
                additional_param['game_time'] = ''
                logger.warning('Unable to get element game time')

            try:
                try:
                    additional_param['game_name'] = driver.find_element(By.TAG_NAME, 'h1').text.replace(' @ ', ' vs ').replace('Quarter', '').replace('1st', '').replace('2nd', '').replace('3rd', '').replace('4th', '').replace('Odds', '')
                    additional_param['game_name'] = additional_param['game_name'].strip()
                except NoSuchElementException:
                    logger.info(f'The game is over')
                    res_upd = update_redis_status(URL, 2)
                    logger.info(res_upd)
                    continue

                logger.info(f'Start scraping game {additional_param.get("game_name")}')

                parsing_start_time = time.time()
                prop_bets_list = []
                additional_param['away_team'], additional_param['home_team'] = split_string(additional_param.get("game_name"))
                additional_param['time_stamp'] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

                allowed_bets = {'Alternates'}
                if '4th' not in additional_param.get('game_time') and additional_param.get('game_time'):                
                    period = additional_param.get('game_time').split()[0]
                    allowed_bets.add(' '.join((period,'Quarter')))    

                for bet_button in previous_bet_bur_buttons:
                    try:
                        title = bet_button.get_attribute('title')
                    except:
                        continue
                    # if title in allowed_bets:
                    if 'Quarter' in title:
                        try:
                            # driver.execute_script("arguments[0].click();", bet_button.find_element(By.TAG_NAME,'a'))
                            bet_button.click()
                        except:
                            logger.warning(f'Tab {title} not clicked')
                            continue

                        tables = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located(
                                (By.XPATH, '//ul[contains(@style, "flex-direction: column;")]')))
                        
                        bets_tables = tables[-1]
                        g_sections = bets_tables.find_elements(By.XPATH, './/li')

                        for idx, single_bet_table in enumerate(g_sections):
                            try:
                                if len(single_bet_table.text) > 0 and len(single_bet_table.text.split('\n')) > 1:
                                    prop_bets_list += parse_prop_bets(single_bet_table.text.split('\n'), additional_param, title)
                                else:
                                    try:
                                        single_bet_table.click()
                                        time.sleep(5)
                                        prop_bets_list += parse_prop_bets(single_bet_table.text.split('\n'), additional_param, title)

                                    except:
                                        continue
                            except:
                                continue
                        

                if not prop_bets_list:
                    continue

                # save data to redis db
                if  len(prop_bets_list) > 0:
                    saving_result = add_data_redis(f'football_fanduel_prop_{file_tail}', prop_bets_list)
                    logger.info(
                        f'The result of saving data: {saving_result}') if saving_result == 'OK' else logger.exception(
                        f'The result of saving data: {saving_result}')            
                count_scraps += 1

                parsing_work_time = time.time() - parsing_start_time
                time.sleep(max(0, update_frequency.total_seconds() - parsing_work_time))

                exception_counter = 0

            except KeyboardInterrupt:
                logger.warning("Keyboard Interrupt. Quit the driver!")
                driver.quit()
                logger.info(f'Module stopped working')
                res_upd = update_redis_status(URL, 2)
                logger.info(res_upd)
                break

            except Exception as e:
                logger.exception(f"Exception in main scraping cycle. {e}")
                exception_counter += 1
                if exception_counter >= 5:
                    driver.quit()
                    logger.exception(f'Script exited after {exception_counter} unsuccessful attempts to execute the main loop')
                    res_upd = update_redis_status(URL, 3)
                    logger.info(res_upd)
                    break
            
            if count_scraps % scrap_step == 0:
                actions_on_page(driver=driver, class_name="")
                if count_scraps == scrap_limit:
                    driver.refresh()                
                    count_scraps = 0

    driver.quit()
    res_upd = update_redis_status(URL, 2)
    logger.info(res_upd)
    logger.warning(f'Module stopped working')


if __name__ == "__main__":
    main()

