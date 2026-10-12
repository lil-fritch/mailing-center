from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.logger import get_logger
from app.models.studio import Studio, CampaignRequest
from app.schemas.email import EmailSendResult
from app.integrations.ai.assistant_client import OpenAIAssistantClient
from app.integrations.mail.mail_sender import MailSender
from app.utils.throttle import pause_between_emails_random
from app.services.campaign_tracker import campaign_tracker
from app.integrations.mail import load_sender_accounts, SenderAccount
from app.services.paralleai import parallel_enricher
from app.database.connection import SessionLocal
from app.database.crud import B2BObjectCRUD
from app.database.models import B2BObject


class DatabaseCampaignService:
    """Сервіс для запуску кампаній з бази даних B2B об'єктів"""

    def __init__(
        self,
        ai_client: Optional[OpenAIAssistantClient] = None,
        mail_sender: Optional[MailSender] = None,
        pause_seconds: Optional[float] = None,
    ) -> None:
        """Ініціалізація сервісу з клієнтами інтеграцій та налаштуваннями пауз"""
        self.logger = get_logger(__name__)
        self.ai_client = ai_client or OpenAIAssistantClient()
        self.mail_sender = mail_sender or MailSender()
        self.pause_seconds = pause_seconds if pause_seconds is not None else settings.email_pause_seconds
        
        # Завантажуємо акаунти відправників з обох JSON файлів
        accounts_1 = load_sender_accounts(settings.sender_accounts_file or "")
        accounts_2 = load_sender_accounts(settings.sender_accounts_file_2 or "")
        
        # Встановлюємо server_id для акаунтів з другого файлу
        for acc in accounts_2:
            acc.server_id = "2"
            
        self.accounts: List[SenderAccount] = accounts_1 + accounts_2
        from_emails_from_accounts = [acc.email for acc in self.accounts if acc.email]
        self.from_emails: List[str] = (
            from_emails_from_accounts if from_emails_from_accounts else (settings.campaign_from_emails or [])
        )
        
        # Визначаємо діапазон пауз
        self.pause_min_seconds: float = (
            settings.email_pause_min_seconds if settings.email_pause_min_seconds is not None else self.pause_seconds
        )
        self.pause_max_seconds: float = (
            settings.email_pause_max_seconds if settings.email_pause_max_seconds is not None else self.pause_seconds
        )

    def _b2b_to_studio(self, b2b_obj: B2BObject) -> Studio:
        """Конвертує B2B об'єкт в Studio з обробкою кодування"""
        def safe_decode(value):
            """Безпечно декодує значення з обробкою помилок кодування"""
            if value is None:
                return None
            try:
                # Просто конвертуємо в рядок і обробляємо помилки
                result = str(value)
                # Якщо є проблемні символи, замінюємо їх
                result = result.encode('utf-8', errors='ignore').decode('utf-8')
                return result
            except Exception:
                return "Unknown" if value is not None else None
        
        return Studio(
            place_id=safe_decode(b2b_obj.place_id),
            title=safe_decode(b2b_obj.name) or "Unknown",
            type=safe_decode(b2b_obj.type) or "unknown",
            phone=safe_decode(b2b_obj.phone),
            emails=[safe_decode(b2b_obj.email)] if b2b_obj.email else None,
            website=safe_decode(b2b_obj.website),
            address=safe_decode(b2b_obj.address) or "",
            city=safe_decode(b2b_obj.city),
            country=safe_decode(b2b_obj.country),
            description=safe_decode(b2b_obj.description),
        )

    async def process_campaign(self, request: CampaignRequest) -> List[EmailSendResult]:
        """Запускає кампанію з бази даних B2B об'єктів"""
        
        # Отримуємо об'єкти з бази даних
        db = SessionLocal()
        try:
            # Використовуємо прямий SQL запит без фільтрів для уникнення проблем з кодуванням
            from sqlalchemy import text
            
            # Простий запит тільки з основними полями
            query = """
            SELECT 
                place_id, 
                name, 
                type, 
                email, 
                phone, 
                website, 
                address, 
                city, 
                country, 
                description 
            FROM b2b_objects 
            WHERE email IS NOT NULL 
            LIMIT :limit
            """
            
            result = db.execute(text(query), {"limit": request.count})
            b2b_objects = []
            
            for row in result:
                # Створюємо об'єкт з рядка
                obj = type('B2BObject', (), {})()
                obj.place_id = str(row[0]) if row[0] else f"unknown_{len(b2b_objects)}"
                obj.name = str(row[1]) if row[1] else f"Studio {len(b2b_objects) + 1}"
                obj.type = str(row[2]) if row[2] else "yoga_studio"
                obj.email = str(row[3]) if row[3] else None
                obj.phone = str(row[4]) if row[4] else None
                obj.website = str(row[5]) if row[5] else None
                obj.address = str(row[6]) if row[6] else "Unknown Address"
                obj.city = str(row[7]) if row[7] else None
                obj.country = str(row[8]) if row[8] else None
                obj.description = str(row[9]) if row[9] else None
                b2b_objects.append(obj)
            
            self.logger.info("Campaign: Retrieved %d objects from database", len(b2b_objects))
            
            # Якщо не знайшли об'єктів, створюємо тестові
            if not b2b_objects:
                self.logger.warning("Campaign: No objects found in database, creating test data")
                for i in range(request.count):
                    obj = type('B2BObject', (), {})()
                    obj.place_id = f"test_studio_{i+1}"
                    obj.name = f"Yoga Studio {i+1}"
                    obj.type = "yoga_studio"
                    obj.email = f"studio{i+1}@example.com"
                    obj.phone = f"+48 123 456 78{i+1}"
                    obj.website = f"https://yogastudio{i+1}.com"
                    obj.address = f"ul. Testowa {i+1}, Warsaw"
                    obj.city = "Warsaw"
                    obj.country = "Poland"
                    obj.description = f"Beautiful yoga studio {i+1} in Warsaw"
                    b2b_objects.append(obj)
                self.logger.info("Campaign: Created %d test objects", len(b2b_objects))
            
        except Exception as e:
            self.logger.error(f"Campaign: Database error: {e}")
            # Створюємо тестові об'єкти якщо база не працює
            b2b_objects = []
            for i in range(request.count):
                obj = type('B2BObject', (), {})()
                obj.place_id = f"test_studio_{i+1}"
                obj.name = f"Yoga Studio {i+1}"
                obj.type = "yoga_studio"
                obj.email = f"studio{i+1}@example.com"
                obj.phone = f"+48 123 456 78{i+1}"
                obj.website = f"https://yogastudio{i+1}.com"
                obj.address = f"ul. Testowa {i+1}, Warsaw"
                obj.city = "Warsaw"
                obj.country = "Poland"
                obj.description = f"Beautiful yoga studio {i+1} in Warsaw"
                b2b_objects.append(obj)
            self.logger.info("Campaign: Created %d test objects as fallback", len(b2b_objects))
        
        finally:
            db.close()
        
        # Конвертуємо B2B об'єкти в Studio
        studios = []
        for obj in b2b_objects:
            try:
                studio = self._b2b_to_studio(obj)
                studios.append(studio)
            except Exception as e:
                self.logger.warning(f"Campaign: failed to convert B2B object {obj.place_id}: {e}")
                continue
        
        if not studios:
            self.logger.error("Campaign: no valid studios could be created")
            return []
        
        self.logger.info("Campaign: successfully converted %d B2B objects to studios", len(studios))
        
        # Запускаємо обробку студій
        return await self._process_studios(studios, request.parsing)

    async def _process_studios(self, studios: List[Studio], parsing: bool) -> List[EmailSendResult]:
        """Обробляє список студій (логіка з EmailCampaignService)"""
        
        results: List[EmailSendResult] = []
        total = len(studios)
        self.logger.info("Campaign: starting processing for %d studios", total)
        campaign_tracker.start(total)

        # Перевіряємо наявність відправних email адрес
        if not self.from_emails:
            self.logger.warning("Campaign: no sender accounts/emails configured; cannot send without FROM address")
            return results

        for index, studio in enumerate(studios):
            batch_index = index + 1
            to_email = None
            if studio.emails and len(studio.emails) > 0:
                to_email = studio.emails[0]

            self.logger.info(
                "Campaign: [%d/%d] studio place_id=%s, title=%s, to=%s",
                batch_index,
                total,
                studio.place_id,
                studio.title,
                to_email,
            )

            if not to_email:
                result = EmailSendResult(
                    success=False,
                    message_id=None,
                    error="No recipient email available",
                )
                results.append(result)
                campaign_tracker.record_result(result)
                self.logger.warning(
                    "Campaign: [%d/%d] no recipient email, skipping place_id=%s",
                    batch_index,
                    total,
                    studio.place_id,
                )
                continue

            try:
                enriched_data = None
                if parsing and studio.website:
                    # Assuming there's a parsing_prompt in campaign (you may need to pass it)
                    parsing_prompt = "Find information about this studio's offerings, classes, retreats, and special programs"
                    enriched_data = await parallel_enricher.enrich_object(
                        website=studio.website,
                        prompt=parsing_prompt,
                        object_name=studio.title
                    )
                email_content = await self.ai_client.generate_email_for_studio(studio, enriched_data)
            except Exception as exc:
                result = EmailSendResult(
                    success=False,
                    message_id=None,
                    error=f"AI generation failed: {str(exc)}",
                )
                results.append(result)
                campaign_tracker.record_result(result)
                self.logger.error(
                    "Campaign: [%d/%d] AI generation failed (place_id=%s, error=%s)",
                    batch_index,
                    total,
                    studio.place_id,
                    str(exc),
                )
                continue

            body_preview = (email_content.body or "")[:200].replace("\n", " ")
            self.logger.info(
                "Campaign: [%d/%d] AI output (place_id=%s, subject=%r, language=%s, body_preview=%r)",
                batch_index,
                total,
                studio.place_id,
                email_content.subject,
                email_content.language,
                body_preview,
            )

            # Спробуємо відправити з різними FROM email адресами
            send_result = None
            attempts = 0
            max_attempts = len(self.from_emails)
            
            while attempts < max_attempts:
                from_email_index = (index + attempts) % len(self.from_emails)
                from_email = self.from_emails[from_email_index]
                attempts += 1

                # Знаходимо акаунт для цього email щоб отримати server_id та ім'я відправника
                account = next((acc for acc in self.accounts if acc.email == from_email), None)
                server_id = account.server_id if account else "1"
                sender_name = None
                if account and account.first_name and account.last_name:
                    sender_name = f"{account.first_name} {account.last_name}"

                self.logger.info(
                    "Campaign: [%d/%d] attempt %d/%d with from_email=%s (server=%s, sender=%s)",
                    batch_index,
                    total,
                    attempts,
                    max_attempts,
                    from_email,
                    server_id,
                    sender_name or "Unknown",
                )

                # Use corporate server if server_id is "2"
                use_corporate = (server_id == "2")
                
                send_result = await self.mail_sender.send_email(
                    email=email_content,
                    from_email=from_email,
                    to_email=to_email,
                    use_corporate=use_corporate,
                    sender_name=sender_name,
                    force_send=True,  # Always send emails from database campaigns, even in dev mode
                )

                if send_result.success:
                    self.logger.info(
                        "Campaign: [%d/%d] email sent successfully with from_email=%s (attempt %d/%d)",
                        batch_index,
                        total,
                        from_email,
                        attempts,
                        max_attempts,
                    )
                    break
                else:
                    self.logger.warning(
                        "Campaign: [%d/%d] send failed with from_email=%s (attempt %d/%d, error=%s)",
                        batch_index,
                        total,
                        from_email,
                        attempts,
                        max_attempts,
                        send_result.error,
                    )
                    
                    # Якщо не остання спроба, пауза перед наступною
                    if attempts < max_attempts:
                        chosen = await self._pause()
                        campaign_tracker.set_last_pause(chosen)

            results.append(send_result)
            campaign_tracker.record_result(send_result)

            # Фінальна пауза після всіх спроб
            chosen = await self._pause()
            campaign_tracker.set_last_pause(chosen)

        self.logger.info("Campaign: finished processing %d studios", total)
        campaign_tracker.finish()
        return results

    async def _pause(self) -> float:
        """Пауза між відправкою листів згідно з налаштованим випадковим діапазоном"""
        chosen = await pause_between_emails_random(self.pause_min_seconds, self.pause_max_seconds)
        self.logger.info("Campaign: paused for %.2fs", chosen)
        return chosen
