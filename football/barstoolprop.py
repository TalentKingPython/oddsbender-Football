import time
from os import environ
from configparser import ConfigParser
from datetime import datetime
from random import randrange

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utilities.logging import get_logger
from utilities.utils import get_driver, str_to_timedelta, add_url_redis, actions_on_page, add_data_redis, read_url_redis

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
# driver.get(URL)

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

def get_team_name(participants_card):
    g_btn = participants_card.find_elements(By.XPATH, ".//button[@data-testid='team-name']")
    away_team = g_btn[0].text.split('\n')[0]
    home_team = g_btn[-1].text.split('\n')[0]
    return [away_team, home_team]
    

def get_period(value):
    if '1st' in value:
        return '1st'
    elif '2nd' in value:
        return '2nd'
    elif '3rd' in value:
        return '3rd'
    elif '4th' in value:
        return '4th'
    else:
        return value

def get_money_bet(additional_param, bets):
    money_dict = []
    for i in range(2):
        if i == 0:
            bet_type = bets[-4]
            odds = bets[-3]
        else:
            bet_type = bets[-2]
            odds = bets[-1]
        prop_one = {
            'SPORT': additional_param.get('sport'),
            'GAME_TYPE': additional_param.get('game_type'),
            'IS_PROP': 1,
            'GAME_NAME': additional_param.get('game_name'),
            'BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Moneyline",
            'BET_TYPE': f"{bet_type}",
            'ODDS': odds,
            'HOME_TEAM': additional_param.get('home_team'),
            'AWAY_TEAM': additional_param.get('away_team'),
            'ALIGNED_BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Moneyline",
            'ALIGNED_BET_TYPE': f"{'Away Team' if i % 2 == 0 else 'Home Team'} {odds}",
            'PERIOD_TYPE': additional_param.get('period_type'),
            'PERIOD_VALUE': additional_param.get('period_value'),
            'PERIOD_TIME': additional_param.get('period_time'),
            'IS_TIMEOUT': additional_param.get('is_timeout'),
            'SPORTS_BOOK': 'Barstoolprop',
            'TIMESTAMP': additional_param.get('time_stamp'),
            'URL': additional_param.get('url')
        }
        money_dict.append(prop_one)

    return money_dict

def get_spread_bet(additional_param, bets):
    spread_dic = []
    for i in range(2):
        if i == 0:
            bet_type = bets[-4]
            odds = bets[-3]
        else:
            bet_type = bets[-2]
            odds = bets[-1]
        prop_one = {
            'SPORT': additional_param.get('sport'),
            'GAME_TYPE': additional_param.get('game_type'),
            'IS_PROP': 1,
            'GAME_NAME': additional_param.get('game_name'),
            'BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Spread",
            'BET_TYPE': f"{bet_type}",
            'ODDS': odds,
            'HOME_TEAM': additional_param.get('home_team'),
            'AWAY_TEAM': additional_param.get('away_team'),
            'ALIGNED_BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Spread",
            'ALIGNED_BET_TYPE': f"{'Away Team' if i % 2 == 0 else 'Home Team'} {odds}",
            'PERIOD_TYPE': additional_param.get('period_type'),
            'PERIOD_VALUE': additional_param.get('period_value'),
            'PERIOD_TIME': additional_param.get('period_time'),
            'IS_TIMEOUT': additional_param.get('is_timeout'),
            'SPORTS_BOOK': 'Barstoolprop',
            'TIMESTAMP': additional_param.get('time_stamp'),
            'URL': additional_param.get('url')
        }
        spread_dic.append(prop_one)

    return spread_dic

def get_total_bet(additional_param, bets):
    spread_dic = []
    for i in range(2):
        if i == 0:
            bet_type = bets[-4]
            odds = bets[-3]
        else:
            bet_type = bets[-2]
            odds = bets[-1]
        prop_one = {
            'SPORT': additional_param.get('sport'),
            'GAME_TYPE': additional_param.get('game_type'),
            'IS_PROP': 1,
            'GAME_NAME': additional_param.get('game_name'),
            'BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Total Points",
            'BET_TYPE': f"{bet_type}",
            'ODDS': odds,
            'HOME_TEAM': additional_param.get('home_team'),
            'AWAY_TEAM': additional_param.get('away_team'),
            'ALIGNED_BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Total Points",
            'ALIGNED_BET_TYPE': bet_type,
            'PERIOD_TYPE': additional_param.get('period_type'),
            'PERIOD_VALUE': additional_param.get('period_value'),
            'PERIOD_TIME': additional_param.get('period_time'),
            'IS_TIMEOUT': additional_param.get('is_timeout'),
            'SPORTS_BOOK': 'Barstoolprop',
            'TIMESTAMP': additional_param.get('time_stamp'),
            'URL': additional_param.get('url')
        }
        spread_dic.append(prop_one)

    return spread_dic


def main():
    module_operate_until = datetime.now() + module_work_duration
    failure_count = 0
    count_scraps = 0

    while datetime.now() < module_operate_until:
        parsing_start_time = time.time()
        url_list = read_url_redis('barstool')

        for u_l in url_list:
            global URL
            global driver
            global file_tail
            try:
                driver.quit()
            except:
                pass
            driver = get_driver(browser)
            URL = u_l[1]
            file_tail = URL.split('/')[-1].split('?')[0]

            driver.get(URL)
            try:
                logger.warning(f'Start scraping urls')
                games_present = 0

                check_capture()

                try:
                    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Football')]"))).click()
                except:
                    logger.warning("No football games")

                for ft_game in driver.find_elements(By.XPATH, "//div[@class='flex w-full justify-between']"):
                    additional_param = {}


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
                    prop_bets_list = []

                    for i in range(len(match_rows)):
                        active_page = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//div[@data-testid='marketplace-shelf-']")))
                        match_rows = active_page.find_elements(By.XPATH, ".//div[contains(@class, 'bg-card-primary rounded p-4')]")
                        participants_card = match_rows[i]

                        l_card_data = participants_card.text.split("\n")[0]
                        if 'LIVE' in l_card_data:
                            g_btn = participants_card.find_element(By.XPATH, ".//button[@data-testid='team-name']")
                            teams = get_team_name(participants_card)
                            g_btn.click()
                            # urls_list.append(driver.current_url)
                            if driver.current_url == URL:
                                additional_param['sport'] = 'Football'
                                additional_param['game_type'] = 'Live'
                                additional_param['url'] = URL
                                additional_param['game_status'] = 1
                                additional_param['is_timeout'] = 0
                                additional_param['time_stamp'] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                                additional_param['away_team'] = teams[0]
                                additional_param['home_team'] = teams[1]
                                additional_param['game_name'] = f"{additional_param['away_team']} vs {additional_param['home_team']}"
                                additional_param['period_type'] = 'Quarter'
                                additional_param['period_time'] = ''
                                additional_param['period_value'] = ''

                                try:
                                    g_time_section = driver.find_element(By.XPATH, ".//div[contains(@class, 'flex h-[80px] min-w-[120px]')]").text
                                    additional_param['period_type'] = 'Quarter'
                                    additional_param['period_time'] = g_time_section.split('\u00b7')[0].strip()
                                    additional_param['period_value'] = get_period(g_time_section)
                                except:
                                    pass

                                try:
                                    g_money_section = driver.find_element(By.XPATH, ".//div[@data-testid='drawer-Moneyline']")
                                    money_vals = g_money_section.text.split('\n')
                                    pre_data = get_money_bet(additional_param, money_vals)
                                    prop_bets_list = prop_bets_list + pre_data
                                except Exception as e:
                                    pass

                                try:
                                    g_spread_section = driver.find_element(By.XPATH, ".//div[@data-testid='drawer-Match Spread']")
                                    spread_vals = g_spread_section.text.split('\n')
                                    pre_data = get_spread_bet(additional_param, spread_vals)
                                    prop_bets_list = prop_bets_list + pre_data
                                except Exception as e:
                                    pass

                                try:
                                    g_total_section = driver.find_element(By.XPATH, ".//div[@data-testid='drawer-Total Points']")
                                    total_vals = g_total_section.text.split('\n')
                                    pre_data = get_total_bet(additional_param, total_vals)
                                    prop_bets_list = prop_bets_list + pre_data

                                except Exception as e:
                                    pass

                        else:
                            continue

                        driver.back()

                    if len(prop_bets_list) > 0:
                        saving_result = add_data_redis(f'football_barstool_prop_{file_tail}', prop_bets_list)
                        logger.info(
                            f'The result of saving data: {saving_result}') if saving_result == 'OK' else logger.exception(
                            f'The result of saving data: {saving_result}')                 

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
                    # break
                    continue
            
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
