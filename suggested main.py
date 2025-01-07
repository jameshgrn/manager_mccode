async def run(self):
    """Main run loop"""
    logger.info("Starting Manager McCode...")
    logger.info(f"Taking screenshots every {SCREENSHOT_INTERVAL_SECONDS} seconds")
    
    error_count = 0
    MAX_ERRORS = 5
    ERROR_RESET_INTERVAL = 300  # 5 minutes
    last_error_time = None

    try:
        while self.running:
            try:
                current_time = datetime.now()

                # Reset error count if enough time has passed
                if last_error_time and (current_time - last_error_time).total_seconds() > ERROR_RESET_INTERVAL:
                    error_count = 0

                # Take screenshot
                image_path = self.image_manager.save_screenshot()
                self.batch_processor.pending_screenshots.append({
                    'path': image_path,
                    'timestamp': current_time
                })

                # Process batch if it's time
                if (current_time - self.batch_processor.last_batch_time).total_seconds() >= self.batch_processor.batch_interval:
                    summaries = await self.batch_processor.process_batch()
                    
                    # Store summaries
                    for summary in summaries:
                        self.db_manager.store_summary(summary)
                    
                    # Show recent summaries
                    recent_summaries = self.db_manager.get_recent_fifteen_min_summaries(hours=1.0)
                    self.display.show_recent_summaries(recent_summaries)
                    
                    self.batch_processor.last_batch_time = current_time

                # Export daily summary if needed
                if current_time.date() != self.last_export_date:
                    summary_file = self.db_manager.export_daily_summary(self.last_export_date)
                    if summary_file:
                        logger.info(f"Daily summary exported to: {summary_file}")
                    self.last_export_date = current_time.date()

                # Memory management: Force garbage collection periodically
                if current_time.minute % 15 == 0 and current_time.second < SCREENSHOT_INTERVAL_SECONDS:
                    import gc
                    gc.collect()

                await asyncio.sleep(SCREENSHOT_INTERVAL_SECONDS)

            except Exception as e:
                error_count += 1
                last_error_time = current_time
                logger.error(f"Error occurred: {str(e)}", exc_info=True)
                
                if error_count >= MAX_ERRORS:
                    logger.critical(f"Too many errors ({error_count}). Shutting down...")
                    self.running = False
                else:
                    logger.warning(f"Error {error_count}/{MAX_ERRORS}. Continuing...")
                    await asyncio.sleep(5)
    finally:
        await self.cleanup()
        logger.info("Manager McCode stopped") 