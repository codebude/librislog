# Progress Tracking

Track your reading progress over time with page-level granularity and visual timelines.

## Dashboard Overview

The dashboard shows:
- A random inspirational quote (if enabled)
- Currently reading books with progress bars
- Next book suggestions from your "Want to Read" list
- Tag cloud showing most common tags in your library

## Updating Progress

### From the Library

For books with a page count set:
1. Open the book detail view
2. Drag the progress slider or type the current page number
3. Progress is saved automatically when you release the slider or blur the input

### Progress Log

Each book maintains a progress log showing the history of page updates:
- Date and time of each update
- Page number reached
- Edit or delete individual log entries

The log is append-only — each update adds a new entry rather than modifying the previous one.

## Timeline Page

The dedicated timeline page shows a chronological view of your reading activity:
- Books started and finished
- Progress updates
- Date conflicts (when a book's start date is after its finish date)

## Date Management

### Date Started / Date Finished

When marking a book as "Read" from "Currently Reading":
- The start date is set automatically (from when you first marked it as "Currently Reading")
- The finish date is set to today

When switching between statuses manually:
- Marking as "Currently Reading" sets the start date
- Marking as "Read" sets the finish date
- Marking as "Want to Read" or "Did Not Finish" clears both dates

### Date Conflicts

If a book has a finish date before its start date, a conflict indicator appears. You can resolve this by editing the dates in the book detail view.

## Reading Percentage

For books with a page count, the detail view shows:
- Current page number
- Total pages
- Reading percentage
- Visual progress bar

## Statistics

Progress data feeds into the statistics dashboard, showing:
- Pages read per month (bar chart)
- Books finished per month and year
- Calendar heatmap of daily reading activity
- Average pages per day

See the [Statistics](./statistics.md) guide for more details.