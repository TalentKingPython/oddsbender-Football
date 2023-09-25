import time
from configparser import ConfigParser
from datetime import datetime
from os import environ

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utilities.logging import get_logger
from utilities.utils import str_to_timedelta, get_driver, add_data_redis, update_redis_status, actions_on_page, text_filter, read_url_redis


# read config file
config_parser = ConfigParser()
config_parser.read('conf/betmgm.conf')
module_conf = config_parser["MODULE"]

# init logging
logger_name = environ.get('football_betmgmprop_get_logger', 'football_betmgm_prop')
# for local logs storage and stdout use DEBUG_FLAG = 1
DEBUG_FLAG = environ.get('PROP_LOG_DEBUG_FLAG', 0)
log_level = environ.get('football_betmgmprop_log_level', 'WARNING')

logger = get_logger(logger_name, DEBUG_FLAG, log_level)

# other variables
# URL = environ['betmgm_prop_url']
# trail = URL.split('-')[-1]
# URL += '?market=-1'
URL = None
file_tail = None


module_work_duration = str_to_timedelta(environ.get('football_betmgmprop_module_work_duration', module_conf.get('module_work_duration')))
update_frequency = str_to_timedelta(environ.get('football_betmgmprop_update_frequency', module_conf.get('update_frequency')))
browser = environ.get('football_betmgmprop_browser', module_conf.get('browser_prop'))

scrap_step = int(environ.get('football_scrap_step', module_conf.get('scrap_step')))
scrap_limit = int(environ.get('football_scrap_limit', module_conf.get('scrap_limit')))

# init web driver
driver = get_driver(browser)
# driver.get(URL)

logger.warning(f'Module started working with parameters:\nURL: {URL}\nmodule_work_duration: {module_work_duration}\nupdate_frequency: {update_frequency}\nbrowser: {browser}\nlogger_name: {logger_name}\nlog_level: {log_level}\nDEBUG_FLAG: {DEBUG_FLAG}')


def parse_gameline_bet(game_data, allowed_bets, period_to_find):
    logger.info(f'Start scraping Gameline')
    soup = BeautifulSoup(game_data, "html.parser")
    all_blocks = soup.find_all("ms-option-panel", {"class": ['option-panel ng-star-inserted']})

    data_list = []
    for ab in all_blocks:
        bet_name = ab.find("div", {"class": ['option-group-name-info-name ng-star-inserted']}).text
        bet_subtype = ab.find_all("span", {"class": ['six-pack-col ng-star-inserted']})
        get_odds = ab.find_all("ms-option", {"class": ['option ng-star-inserted']})

        if bet_name.lower() in allowed_bets:
            odds_list = []
            subtype_odds_list = []
            for go in get_odds:
                try:
                    subtype_odds = go.find("div", {"class": ['name ng-star-inserted']}).text
                except:
                    subtype_odds = ''
                try:
                    odds = go.find("div", {"class": ['value option-value ng-star-inserted']}).text
                except:
                    odds = ''
                subtype_odds_list.append(subtype_odds)
                odds_list.append(odds)

            data_list.append([bet_name, [i.text for i in bet_subtype], subtype_odds_list, odds_list])

    list_dict = []

    for dl in data_list:
        if len(dl[1]) in {2,3}:
            for bt in dl[1]:
                idx = dl[1].index(bt)                 
                list_dict.append([' '.join((dl[0], period_to_find, bt)), '||', ' ', dl[2][idx], '||', dl[3][idx], 'Away Team'])
                list_dict.append([' '.join((dl[0], period_to_find, bt)), '||', ' ', dl[2][idx + len(dl[1])], '||', dl[3][idx + len(dl[1])], 'Home Team'])
        else:
            num = 0
            for sod, od in zip(dl[2], dl[3]):
                sod = sod.upper().replace('UNDER', 'U').replace('OVER', 'O')
                list_dict.append([' '.join(('Alternative', dl[0])), '||', '', sod, '||', od, 'Away Team' if num % 2 == 0 else 'Home Team'])
                num += 1

    return list_dict


def gen_dict(additional_param, g_title, g_scores):

    logger.info(f'Start generating dict')
    popular_bets_list = []

    for idx, g_t in enumerate(g_title):
        if g_t == 'Spread':
            bet_v = g_scores[idx * 3].split('\n')
            try:
                prop_one = {
                    'SPORT': additional_param.get('sport'),
                    'GAME_TYPE': additional_param.get('game_type'),
                    'IS_PROP': 1,
                    'GAME_NAME': additional_param.get('game_name'),
                    'BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Spread",
                    'BET_TYPE': f"{additional_param.get('away_team') if idx % 2 == 0 else additional_param.get('home_team')} {bet_v[0]}",
                    'ODDS': bet_v[1],
                    'HOME_TEAM': additional_param.get('away_team'),
                    'AWAY_TEAM': additional_param.get('home_team'),
                    'ALIGNED_BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Spread",
                    'ALIGNED_BET_TYPE': f"{'Away Team' if idx % 2 == 0 else 'Home Team'} {bet_v[0]}",
                    'PERIOD_TYPE': additional_param.get('period_type'),
                    'PERIOD_VALUE': additional_param.get('period_value'),
                    'PERIOD_TIME': additional_param.get('period_time'),
                    'IS_TIMEOUT': additional_param.get('is_timeout'),
                    'SPORTS_BOOK': 'Betmgm',
                    'TIMESTAMP': additional_param.get('time_stamp'),
                    'URL': URL
                }

                popular_bets_list.append(prop_one)
            except:
                pass
        
        elif g_t == 'Total':
            try:
                bet_v = g_scores[1].split('\n') if idx == 0 else g_scores[4].split('\n')
                prop_one = {
                    'SPORT': additional_param.get('sport'),
                    'GAME_TYPE': additional_param.get('game_type'),
                    'IS_PROP': 1,
                    'GAME_NAME': additional_param.get('game_name'),
                    'BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Total Points",
                    'BET_TYPE': bet_v[0],
                    'ODDS': bet_v[1],
                    'HOME_TEAM': additional_param.get('away_team'),
                    'AWAY_TEAM': additional_param.get('home_team'),
                    'ALIGNED_BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Total Points",
                    'ALIGNED_BET_TYPE': bet_v[0],
                    'PERIOD_TYPE': additional_param.get('period_type'),
                    'PERIOD_VALUE': additional_param.get('period_value'),
                    'PERIOD_TIME': additional_param.get('period_time'),
                    'IS_TIMEOUT': additional_param.get('is_timeout'),
                    'SPORTS_BOOK': 'Betmgm',
                    'TIMESTAMP': additional_param.get('time_stamp'),
                    'URL': URL
                }
                popular_bets_list.append(prop_one)
            except:
                pass

        elif g_t == 'Money':
            try:
                bet_v = g_scores[2] if idx == 0 else g_scores[5]
                prop_one = {
                    'SPORT': additional_param.get('sport'),
                    'GAME_TYPE': additional_param.get('game_type'),
                    'IS_PROP': 1,
                    'GAME_NAME': additional_param.get('game_name'),
                    'BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Moneyline",
                    'BET_TYPE': f"{additional_param.get('away_team') if idx % 2 == 0 else additional_param.get('home_team')}",
                    'ODDS': bet_v,
                    'HOME_TEAM': additional_param.get('away_team'),
                    'AWAY_TEAM': additional_param.get('home_team'),
                    'ALIGNED_BET_NAME': f"{additional_param.get('period_value')} {additional_param.get('period_type')} Moneyline",
                    'ALIGNED_BET_TYPE': f"{'Away Team' if idx % 2 == 0 else 'Home Team'}",
                    'PERIOD_TYPE': additional_param.get('period_type'),
                    'PERIOD_VALUE': additional_param.get('period_value'),
                    'PERIOD_TIME': additional_param.get('period_time'),
                    'IS_TIMEOUT': additional_param.get('is_timeout'),
                    'SPORTS_BOOK': 'Betmgm',
                    'TIMESTAMP': additional_param.get('time_stamp'),
                    'URL': URL
                }
                popular_bets_list.append(prop_one)
            except:
                pass

    return popular_bets_list
 
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


def main():
    module_operate_until = datetime.now() + module_work_duration
    exception_counter = 0
    count_scraps = 0

    while datetime.now() < module_operate_until:
        urls = read_url_redis('betmgm')
        for redis_url in urls:
            global URL
            global driver
            global file_tail
            try:
                driver.quit()
            except:
                pass
            driver = get_driver(browser)
            URL = redis_url[1]
            driver.get(URL)
            file_tail = URL.split('/')[-1]
        
            try:
                parsing_start_time = time.time()
                logger.info(f'Start scraping...')
                additional_param = {}

                # check if the game is not over
                try:
                    game_status = WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
                        (By.XPATH, "//*[@class='scoreboard-message']"))).text
                except:
                    try:
                        game_status = WebDriverWait(driver, 1).until(EC.visibility_of_element_located(
                            (By.CSS_SELECTOR, '.scoreboard-timer'))).text
                    except:
                        game_status = ''

                if 'Starting in' in game_status:
                    time_wait = int(''.join(x for x in game_status if x.isdigit()))
                    logger.warning(f'The game {game_status}, waiting...')
                    time.sleep(time_wait * 60)
                
                popular_bets_list = []

                if game_status:
                    additional_param['sport'] = 'Football'
                    additional_param['game_type'] = 'Live'
                    try:
                        additional_param['game_time'] = driver.find_element(
                            By.XPATH, "//*[@class='period-name ng-star-inserted']").text
                    except:
                        additional_param['game_time'] = 'Starting now'
                    

                    additional_param['game_status'] = game_status
                    additional_param['is_timeout'] = 1 if game_status == 'Timeout' else 0
                    additional_param['is_timeout'] = 1 if additional_param['game_time'] in {'Halftime', 'Intermission'} else additional_param['is_timeout']
                    additional_param['time_stamp'] = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

                    get_teams = driver.find_elements(By.XPATH, "//div[@class='participant-name']")
                    additional_param['home_team'], additional_param['away_team'] = [i.text for i in get_teams][:2]
                    additional_param['game_name'] = f"{additional_param['away_team']} vs{additional_param['home_team']}"

                    g_buttons = driver.find_element(By.XPATH, "//ul[@class='pill-bar-container']")
                    check_quarter = False
                    try:
                        quater_btn = g_buttons.find_element(By.XPATH, ".//li/span[contains(text(), 'Quarters')]")
                        quater_btn.click()
                        check_quarter = True
                    except Exception as e:
                        pass
            
                    if check_quarter:
                        try:
                            get_all_props = driver.find_element(By.XPATH, "//*[@class='option-group-list ng-star-inserted']")
                        except:
                            logger.info(f'The game has ended')
                            res_upd = update_redis_status(URL.replace('?market=-1', ''), 2)
                            logger.info(res_upd)
                            # break
                            continue


                        try:
                            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//ms-option-panel[@class='option-panel ng-star-inserted']")))
                            g_section = driver.find_element(By.XPATH,"//ms-option-panel[@class='option-panel ng-star-inserted']")
                            
                            g_header = g_section.find_element(By.XPATH, ".//div[@class='header-content']").text
                            additional_param['period_value'] = get_period(g_header)
                            additional_param['period_type'] = 'Quarter'
                            additional_param['period_time'] = additional_param['game_time']

                            g_title_str = g_section.find_element(By.XPATH, ".//div[@class='option-group-header']").text
                            g_title = g_title_str.split('\n')
                            g_score_str = g_section.find_elements(By.XPATH, ".//div[@class='option-indicator']")
                            g_scores = [g_s.text for g_s in g_score_str]
                            popular_bets_list  = gen_dict(additional_param, g_title, g_scores)
                        except Exception as e:
                            pass

                        if not popular_bets_list:
                            time.sleep(10)
                            continue

                        # save data to redis db
                        saving_result = add_data_redis(f'football_betmgm_prop_{trail}', popular_bets_list)
                        logger.info(
                            f'The result of saving data: {saving_result}') if saving_result == 'OK' else logger.exception(
                            f'The result of saving data: {saving_result}')                
                        count_scraps += 1

                        parsing_work_time = time.time() - parsing_start_time
                        time.sleep(max(0, update_frequency.total_seconds() - parsing_work_time))
                        time.sleep(10)

                        exception_counter = 0

                if not game_status:
                    logger.info(f'The game has ended')
                    res_upd = update_redis_status(URL.replace('?market=-1', ''), 2)
                    logger.info(res_upd)
                    continue

            except KeyboardInterrupt:
                logger.warning("Keyboard Interrupt. Quit the driver!")
                driver.close()
                logger.info(f'Module stopped working')
                res_upd = update_redis_status(URL.replace('?market=-1', ''), 2)
                logger.info(res_upd)
                break

            except Exception as e:
                logger.exception(f"Exception in main scraping cycle. {e}")
                exception_counter += 1
                if exception_counter >= 5:
                    driver.close()
                    logger.exception(
                        f'Script exited after {exception_counter} unsuccessful attempts to execute the main loop')
                    res_upd = update_redis_status(URL.replace('?market=-1', ''), 3)
                    logger.info(res_upd)
                    continue
            
            if count_scraps % scrap_step == 0:
                actions_on_page(driver=driver, class_name="option-group-name-info-name ng-star-inserted")
                if count_scraps == scrap_limit:
                    driver.refresh()                
                    count_scraps = 0

        driver.close()
        res_upd = update_redis_status(URL.replace('?market=-1', ''), 2)
        logger.info(res_upd)
        logger.warning(f'Module stopped working')


if __name__ == "__main__":
    main()
