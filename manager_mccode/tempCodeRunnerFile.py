import asyncio
import traceback
from datetime import datetime
from manager_mccode.services.database import DatabaseManager
from manager_mccode.services.image import ImageManager
from manager_mccode.services.batch import BatchProcessor
from manager_mccode.services.analyzer import GeminiAnalyzer
from manager_mccode.config.settings import SCREENSHOT_INTERVAL_SECONDS

async def main():
    db_manager = DatabaseManager()
    image_manager = ImageManager()
    batch_processor = BatchProcessor()
    
    print("\nStarting screen activity monitor...")
    print(f"Taking screenshots every {SCREENSHOT_INTERVAL_SECONDS} seconds")
    print("Processing in batches")
    print("Press Ctrl+C to exit\n")
    
    last_export_date = datetime.now().date()
    
    while True:
        try:
            current_time = datetime.now()
            
            # Take screenshot
            image_path = image_manager.save_screenshot()
            batch_processor.pending_screenshots.append({
                'path': image_path,
                'timestamp': current_time
            })
            
            # Process batch if it's time
            if (current_time - batch_processor.last_batch_time).total_seconds() >= batch_processor.batch_interval:
                print("\nProcessing batch...")
                summaries = await batch_processor.process_batch()
                
                # Store summaries
                for summary in summaries:
                    db_manager.store_summary(summary)
                
                batch_processor.last_batch_time = current_time
                print(f"Processed {len(summaries)} screenshots")
            
            # Export daily summary if needed
            if current_time.date() != last_export_date:
                summary_file = db_manager.export_daily_summary(last_export_date)
                if summary_file:
                    print(f"\nDaily summary exported to: {summary_file}")
                last_export_date = current_time.date()
            
            # Wait for next screenshot
            await asyncio.sleep(SCREENSHOT_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            # Process any remaining screenshots
            if batch_processor.pending_screenshots:
                summaries = await batch_processor.process_batch()
                for summary in summaries:
                    db_manager.store_summary(summary)
            break
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            print(traceback.format_exc())
            await asyncio.sleep(5)
            continue

    # Cleanup before exit
    image_manager.cleanup_old_images(max_age_minutes=0)

if __name__ == "__main__":
    asyncio.run(main()) 