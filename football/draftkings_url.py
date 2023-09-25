from os import environ
import time
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
config_parser.read('conf/draftkings.conf')
module_conf = config_parser["MODULE"]

# init logging
logger_name = environ.get('football_draftkings_url_get_logger', 'football_draftkings_url_logger')
# for local logs storage and stdout use DEBUG_FLAG = 1
DEBUG_FLAG = environ.get('football_draftkings_url_DEBUG_FLAG', 0)
log_level = environ.get('football_draftkings_url_log_level', 'WARNING')

logger = get_logger(logger_name, DEBUG_FLAG, log_level)

# other variables
URL = environ.get('football_draftkings_url', module_conf.get('URL'))
module_work_duration = str_to_timedelta(environ.get('football_draftkings_url_module_work_duration', module_conf.get('module_work_duration')))
update_frequency = str_to_timedelta(environ.get('bfootball_draftkings_url_update_frequency', module_conf.get('update_frequency')))
browser = environ.get('football_draftkings_url_browser', module_conf.get('browser_url'))

scrap_step = int(environ.get('football_scrap_step', module_conf.get('scrap_step')))
scrap_limit = int(environ.get('football_scrap_limit', module_conf.get('scrap_limit')))

# init web driver
driver = get_driver(browser)
driver.get(URL)

logger.warning(f'Module started working with parameters:\nURL: {URL}\nmodule_work_duration: {module_work_duration}\nupdate_frequency: {update_frequency}\nbrowser: {browser}\nlogger_name: {logger_name}\nlog_level: {log_level}\nDEBUG_FLAG: {DEBUG_FLAG}')


def main():
    module_operate_until = datetime.now() + module_work_duration

    failure_count = 0
    count_scraps = 0

    while datetime.now() < module_operate_until:
        parsing_start_time = time.time()
        try:
            logger.info(f'Start scraping urls')
            check_game = False

            try:
                # check if football is in live games
                check_game_list = WebDriverWait(driver, 10).until(EC.visibility_of_all_elements_located(
                    (By.XPATH, "//span[@class='sportsbook-tabbed-subheader__tab']")))
                for fg in check_game_list:
                    if fg.text == 'FOOTBALL':
                        check_game = True
                        break
            except Exception as error:
                logger.exception(f"Problem with extracting the name of the game\n{error}")

            if check_game:
                hidden_games = True
                while hidden_games:
                    try:
                        get_hidden_games = WebDriverWait(driver, 3).until(EC.visibility_of_all_elements_located(
                            (By.XPATH, "//div[@class='sportsbook-featured-accordion__wrapper sportsbook-accordion__wrapper collapsed']")))
                        if len(get_hidden_games) > 0:
                            [i.click() for i in get_hidden_games]
                    except:
                        hidden_games = False

                # get all live games    
                game_sections = driver.find_elements(By.XPATH, ".//div[contains(@class, 'sportsbook-featured-accordion__wrapper sportsbook-accordion__wrapper')]")
                urls_list = []
                for g_s in game_sections:    

                    league_section = g_s.find_element(By.XPATH, ".//div[@class='sportsbook-header__title']")
                    league_txt = league_section.text
                    if 'college football' in league_txt.lower().strip():
                        league_txt = 'NCAAF'
                    elif 'nfl' in league_txt.lower().strip():
                        league_txt = 'NFL'
                    else:
                        continue

                    games_on_initial_page = WebDriverWait(g_s, 10).until(EC.visibility_of_all_elements_located(
                            (By.XPATH, "//a[@class='event-cell-link']")))
                    for game in games_on_initial_page:
                        if game.get_attribute('href') not in urls_list:
                            urls_list.append(game.get_attribute('href'))

                    logger.info(f"Found {len(urls_list)} url's")

                # save data to redis db
                for rd_url in urls_list:
                    stream_name = rd_url.split('/')
                    saving_result = add_url_redis(rd_url, 'draftkings', f'football_draftkings_prop_{stream_name[-1]}')
                    logger.info(f'Result: {saving_result}')                
                count_scraps += 1

                # reset unsuccessful attempts in main loop
                failure_count = 0

            if not check_game:
                logger.warning('There are no live games, waiting for some time and trying again')
                time.sleep(randrange(4000, 12000, 10) / 1000)
                driver.get(URL)
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
            actions_on_page(driver=driver, class_name="sportsbook-tabbed-subheader__tab selected")
            if count_scraps == scrap_limit:
                driver.refresh()                
                count_scraps = 0

        parsing_work_time = time.time() - parsing_start_time
        time.sleep(max(0, update_frequency.total_seconds() - parsing_work_time))

    driver.quit()
    logger.warning('Script successfully ended working at the set time')


if __name__ == "__main__":
    main()
