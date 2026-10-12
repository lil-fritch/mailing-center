from app.core.logger import logger
from app.core.errors import AppError
from app.core.config import settings
from app.schemas.email import EmailMessageIn, EmailAccount
import asyncio
import logging
import time
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import html

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

class DriverManager:
    """Менеджер для створення та налаштування Selenium драйвера"""
    
    @staticmethod
    def _find_chrome_binary() -> Optional[str]:
        """Знаходить шлях до Chrome/Chromium binary на системі"""
        # Якщо вказано в конфігурації - використовуємо його
        if settings.SELENIUM_CHROME_BINARY:
            binary_path = Path(settings.SELENIUM_CHROME_BINARY)
            if binary_path.exists() and binary_path.is_file():
                return str(binary_path)
            logger.warning(f"Chrome binary from config not found: {settings.SELENIUM_CHROME_BINARY}")
        
        # Перевіряємо стандартні місця на Linux
        common_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/local/bin/google-chrome",
            "/usr/local/bin/chromium",
            "/snap/bin/chromium",
        ]
        
        for path in common_paths:
            if Path(path).exists():
                logger.info(f"Found Chrome binary at: {path}")
                return path
        
        # Спробуємо знайти через which/where
        binary_names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]
        for name in binary_names:
            found_path = shutil.which(name)
            if found_path:
                logger.info(f"Found Chrome binary via which: {found_path}")
                return found_path
        
        return None
    
    @staticmethod
    def create_chrome_driver(headless: bool = True) -> webdriver.Chrome:
        """Створює Chrome драйвер з оптимальними налаштуваннями для серверного використання"""
        
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless")
        
        # Базові налаштування для стабільної роботи
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-images")  # Прискорення завантаження
        chrome_options.add_argument("--disable-notifications")
        
        # Налаштування User-Agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Розмір вікна
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Встановлюємо preferences
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "media_stream": 2,
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Вказуємо шлях до Chrome binary, якщо знайдено
        chrome_binary = DriverManager._find_chrome_binary()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info(f"Using Chrome binary: {chrome_binary}")
        else:
            logger.warning("Chrome binary not found in standard locations. Selenium will try to find it automatically.")
        
        try:
            # Спробуємо використати системний chromedriver або завантажити автоматично
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.warning(f"Не вдалося використати ChromeDriverManager: {e}")
            # Якщо не вдалося, спробуємо використати системний chromedriver
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                error_msg = (
                    f"Cannot find Chrome binary. Please install Chrome/Chromium on the server or "
                    f"set SELENIUM_CHROME_BINARY in .env file. "
                    f"Error: {str(e2)}"
                )
                logger.error(error_msg)
                raise AppError(
                    message=error_msg,
                    details={"error": str(e2), "chrome_binary": chrome_binary}
                )
        
        # Налаштування таймаутів
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(30)
        
        return driver


class OPPLSender:
    """Клас для відправки листів через Onet.pl використовуючи Selenium"""
    
    def __init__(self, account):  # EmailAccount
        self.account = account
        self.driver = None
        self.wait = None
        # Унікальна папка для кожного запуску і для кожного акаунта
        run_id = datetime.now().strftime("%d%m%y_%H_%M_") + uuid.uuid4().hex[:6]

        safe_email = str(self.account.email).replace("@", "_at_").replace(".", "_")
        self.screenshots_dir = Path("selenium_data/screenshots") / safe_email / run_id
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def _compose_button_locator(self):
        """Повертає локатор для кнопки 'Написати повідомлення' (PL/UA)"""
        button_texts = ["Napisz wiadomość", "Napisać wiadomość", "Napisać wiadomość!", "Напиши повідомлення", "Napisz wiadomość!", "Написати повідомлення"]
        span_conditions = " or ".join([f"contains(normalize-space(.), '{text}')" for text in button_texts])
        element_conditions = " or ".join([f"contains(normalize-space(.), '{text}')" for text in button_texts])
        xpath = (
            "("
            f"//button[{element_conditions} or .//span[{span_conditions}]]"
            f" | //a[@role='button' and ({element_conditions})]"
            f" | //div[@role='button' and ({element_conditions})]"
            f" | //span[@role='button' and ({element_conditions})]"
            ")"
        )
        return (By.XPATH, xpath)

    def _wait_for_compose_button(self, timeout: int = 60):
        locator = self._compose_button_locator()
        wait = WebDriverWait(self.driver, timeout)
        wait.until(EC.presence_of_element_located(locator))
        wait.until(EC.element_to_be_clickable(locator))
        return locator

    def _send_button_locator(self):
        """Повертає локатор для кнопки 'Wyślij' (PL/UA)"""
        button_texts = ["Wyślij", "Wyślij wiadomość", "Надіслати"]
        text_conditions = " or ".join([f"contains(normalize-space(), '{text}')" for text in button_texts])
        xpath = f"//button[.//span[{text_conditions}]]"
        return (By.XPATH, xpath)

    async def _handle_intro_popup(self, context: str = ""):
        """Закриває popup 'Przejdź do serwisu', якщо він з'явився"""
        if not self.driver:
            return
        locator = (By.CSS_SELECTOR, "button.cmp-button_button.cmp-intro_acceptAll")
        wait = WebDriverWait(self.driver, 5)
        try:
            button = wait.until(EC.element_to_be_clickable(locator))
            button.click()
            logger.info(f"Закрили popup 'Przejdź do serwisu' ({context})")
            await asyncio.sleep(0.5)
        except TimeoutException:
            logger.debug(f"Popup відсутній ({context})")

    async def _select_recipient_suggestion(self, email: str) -> bool:
        """Клікає на підказку з email, якщо вона з'явилась"""
        safe_email = email.replace("'", "\\'")
        suggestion_xpath = (
            f"//ul[contains(@class,'is-visible')]//button"
            f"[.//div[contains(text(), '{safe_email}')]]"
        )
        suggestion_locator = (By.XPATH, suggestion_xpath)
        try:
            suggestion = self.wait.until(EC.element_to_be_clickable(suggestion_locator))
            suggestion.click()
            logger.info(f"Обрано підказку email: {email}")
            await asyncio.sleep(1)
            return True
        except TimeoutException:
            logger.info("Підказка для email не з'явилась — пропускаємо")
            return False

    async def _confirm_recipient_entry(self, email: str):
        """Підтверджує введення email навіть без підказки"""
        suggestion_selected = await self._select_recipient_suggestion(email)
        if suggestion_selected:
            return
        await asyncio.sleep(0.5)
        try:
            container = self.driver.find_element(By.ID, "NEW_MAIL_FORMS_CONTAINER_ID")
            self.driver.execute_script("arguments[0].click();", container)
            logger.info("Клік поза полем для підтвердження адреси")
        except Exception:
            try:
                field = self.driver.find_element(By.ID, "field-recipient-to")
                field.send_keys(Keys.TAB)
                logger.info("TAB для підтвердження адреси")
            except Exception as e:
                logger.warning(f"Не вдалося примусово підтвердити адресу: {e}")
        await asyncio.sleep(0.5)
        
    def _take_screenshot(self, name: str):
        """Робить скріншот для дебагу"""
        try:
            if self.driver:
                screenshot_path = self.screenshots_dir / f"{name}_{int(time.time())}.png"
                self.driver.save_screenshot(str(screenshot_path))
                logger.info(f"Скріншот збережено: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Не вдалося зробити скріншот: {e}")
    
    def _setup_driver(self, headless: bool = True):
        """Налаштовує Selenium драйвер"""
        try:
            self.driver = DriverManager.create_chrome_driver(headless=headless)
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("Драйвер успішно налаштовано")
        except Exception as e:
            logger.error(f"Помилка налаштування драйвера: {e}")
            raise
    
    def _cleanup_driver(self):
        """Закриває драйвер"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Драйвер закрито")
            except Exception as e:
                logger.warning(f"Помилка закриття драйвера: {e}")
            finally:
                self.driver = None
                self.wait = None
    
    async def _wait_and_click(self, locator, timeout: int = 20, screenshot_name: str = None):
        """Очікує елемент та клікає на нього"""
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            if screenshot_name:
                self._take_screenshot(f"{screenshot_name}")
            element.click()
            logger.info(f"Клік по елементу: {locator}")
            await asyncio.sleep(1)  # Невелика пауза після кліку
            return element
        except TimeoutException:
            self._take_screenshot(f"timeout_{screenshot_name or 'click'}")
            raise TimeoutException(f"Елемент не знайдено або не кликабельний: {locator}")
    
    async def _wait_and_type(self, locator, text: str, timeout: int = 20, clear_first: bool = True):
        """Очікує елемент та вводить текст"""
        try:
            element = self.wait.until(EC.presence_of_element_located(locator))
            if clear_first:
                element.clear()
            element.send_keys(text)
            logger.info(f"Введено текст в елемент: {locator}")
            await asyncio.sleep(0.5)
            return element
        except TimeoutException:
            self._take_screenshot("timeout_type")
            raise TimeoutException(f"Елемент для введення не знайдено: {locator}")
    
    async def _login(self):
        """Виконує вхід в акаунт"""
        logger.info("Початок входу в акаунт")
        
        # 1. Перехід на сайт
        self.driver.get("https://poczta.onet.pl/")
        await asyncio.sleep(2)
        self._take_screenshot("01_main_page")
        
        # 2. Закриття "Przejdź до serwisu"
        await self._handle_intro_popup("після відкриття")
        
        await asyncio.sleep(2)
        self._take_screenshot("03_after_accept")
        
        # 3. Введення email
        email_field = (By.ID, "email")
        await self._wait_and_type(email_field, self.account.email)
        self._take_screenshot("04_email_entered")
        
        # 4. Натискання submit після email
        submit_button = (By.CSS_SELECTOR, "button[type='submit']")
        await self._wait_and_click(submit_button, screenshot_name="05_email_submit")
        await self._handle_intro_popup("після email submit")
        
        await asyncio.sleep(2)
        
        # 5. Введення паролю
        password_field = (By.ID, "password")
        await self._wait_and_type(password_field, self.account.password)
        self._take_screenshot("06_password_entered")
        
        # 6. Натискання submit після паролю
        await self._wait_and_click(submit_button, screenshot_name="07_password_submit")
        await self._handle_intro_popup("після password submit")
        
        await asyncio.sleep(2)
        
        # 7. Оновлення сторінки
        logger.info("Оновлення сторінки")
        self.driver.get("https://poczta.onet.pl/")
        await self._handle_intro_popup("після refresh")
        inbox_locator = self._wait_for_compose_button()
        self._take_screenshot("08_after_refresh")
        logger.info("Вхід в акаунт завершено")
    
    async def _compose_and_send_email(self, message):  # EmailMessageIn
        """Створює та відправляє лист"""
        logger.info("Початок створення листа")
        
        # 8. Натискання на "Napisz wiadomość"
        await self._handle_intro_popup("перед compose")
        compose_button = self._wait_for_compose_button()
        await self._wait_and_click(compose_button, screenshot_name="09_compose_button")
        
        await asyncio.sleep(2)
        self._take_screenshot("10_compose_form")
        
        # 9. Введення адреси отримувача
        recipient_field = (By.CSS_SELECTOR, "#field-recipient-to")
        email_address = message.to_email

        # Знаходимо елемент
        recipient_element = self.wait.until(EC.presence_of_element_located(recipient_field))
        recipient_element.click()

        # ПРИБИРАЄМО AWAIT: execute_script є синхронною функцією
        self.driver.execute_script("arguments[0].value = arguments[1];", recipient_element, email_address)
        self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", recipient_element)

        # send_keys також синхронна функція
        recipient_element.send_keys(" ")
        await asyncio.sleep(1)
        await self._confirm_recipient_entry(email_address)
        
        self._take_screenshot("11_recipient_entered")
        
        # 10. Введення теми
        subject_field = (By.CSS_SELECTOR, "#new-mail-subject-item")
        await self._wait_and_type(subject_field, message.subject)
        self._take_screenshot("12_subject_entered")
        
        # 11. Введення тіла листа
        body_field = (By.ID, "newmail-editor")
        body_element = self.wait.until(EC.presence_of_element_located(body_field))
        await asyncio.sleep(1)
        self.driver.execute_script("arguments[0].focus();", body_element)
        
        email_body = message.body or ""
        body_html = html.escape(email_body).replace("\n", "<br>") if email_body else "<br>"
        message_html = f"<div style='font-size: 16px;'>{body_html}</div>"
        
        signature_html = self.driver.execute_script("""
            const editor = arguments[0];
            const signatureNode = editor.querySelector('.js_WEBMAIL_SIGN_CONTAINER');
            return signatureNode ? signatureNode.outerHTML : '';
        """, body_element)
        separator_html = "<div class=\"sign-separator\"><br></div>"
        
        self.driver.execute_script("""
            const editor = arguments[0];
            const messageHtml = arguments[1];
            const signatureHtml = arguments[2];
            const separatorHtml = arguments[3];
            editor.innerHTML = messageHtml + (signatureHtml ? separatorHtml + signatureHtml : '');
            const selection = window.getSelection();
            if (selection) {
                selection.removeAllRanges();
                const range = document.createRange();
                range.selectNodeContents(editor);
                range.collapse(false);
                selection.addRange(range);
            }
        """, body_element, message_html, signature_html, separator_html if signature_html else "")
        self._take_screenshot("13_body_entered")
        
        # 12. Відправка листа
        send_button = self._send_button_locator()
        await self._wait_and_click(send_button, screenshot_name="14_send_button")
        
        await asyncio.sleep(3)
        self._take_screenshot("15_after_send")
        
        logger.info("Лист відправлено успішно")
    
    async def send_email(self, message) -> None:  # EmailMessageIn -> None
        """Основний метод для відправки листа з повторною спробою"""
        max_attempts = 2
        retry_delay = 3
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Початок відправки листа до {message.to_email} (спроба {attempt}/{max_attempts})")
                
                # Налаштування драйвера
                self._setup_driver(headless=True)  # Встановіть False для дебагу
                
                # Вхід в акаунт
                await self._login()
                
                # Створення та відправка листа
                await self._compose_and_send_email(message)
                
                logger.info(f"Лист успішно відправлено до {message.to_email}")
                return
            
            except TimeoutException as e:
                logger.error(f"Selenium timeout error (спроба {attempt}): {e}")
                self._take_screenshot(f"error_timeout_attempt_{attempt}")
                if attempt >= max_attempts:
                    raise AppError(
                        message=f"Selenium timeout - page elements not found: {str(e)}",
                        details={"error": str(e)}
                    )
            
            except WebDriverException as e:
                logger.error(f"WebDriver error (спроба {attempt}): {e}")
                self._take_screenshot(f"error_webdriver_attempt_{attempt}")
                if attempt >= max_attempts:
                    raise AppError(
                        message=f"WebDriver error: {str(e)}",
                        details={"error": str(e)}
                    )
            
            except Exception as e:
                logger.error(f"Unexpected error during Selenium sending (спроба {attempt}): {e}")
                self._take_screenshot(f"error_final_attempt_{attempt}")
                if attempt >= max_attempts:
                    raise AppError(
                        message=f"Selenium error: {str(e)}",
                        details={"error": str(e)}
                    )
            
            finally:
                # Завжди закриваємо драйвер
                self._cleanup_driver()
            
            if attempt < max_attempts:
                logger.info(f"Повторна спроба відправки через {retry_delay}с...")
                await asyncio.sleep(retry_delay)