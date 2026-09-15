import type {
	PublicProfileSectionKey,
	PublicProfileStatisticsKey,
	PublicProfileVisibilityConfig
} from '$lib/types';

export interface PublicProfileSectionDef {
	key: PublicProfileSectionKey;
	i18nKey: string;
	tooltipKey: string;
	/** Enabled by default when a new share link is created. */
	defaultOn: boolean;
}

export const PUBLIC_PROFILE_SECTIONS: PublicProfileSectionDef[] = [
	{
		key: 'username',
		i18nKey: 'publicProfile.sections.username',
		tooltipKey: 'publicProfile.sections.usernameTooltip',
		defaultOn: true
	},
	{
		key: 'user_info',
		i18nKey: 'publicProfile.sections.userInfo',
		tooltipKey: 'publicProfile.sections.userInfoTooltip',
		defaultOn: true
	},
	{
		key: 'currently_reading',
		i18nKey: 'publicProfile.sections.currentlyReading',
		tooltipKey: 'publicProfile.sections.currentlyReadingTooltip',
		defaultOn: true
	},
	{
		key: 'last_read',
		i18nKey: 'publicProfile.sections.lastRead',
		tooltipKey: 'publicProfile.sections.lastReadTooltip',
		defaultOn: false
	},
	{
		key: 'reading_timeline',
		i18nKey: 'publicProfile.sections.readingTimeline',
		tooltipKey: 'publicProfile.sections.readingTimelineTooltip',
		defaultOn: false
	},
	{
		key: 'full_library',
		i18nKey: 'publicProfile.sections.fullLibrary',
		tooltipKey: 'publicProfile.sections.fullLibraryTooltip',
		defaultOn: false
	},
	{
		key: 'statistics',
		i18nKey: 'publicProfile.sections.statistics',
		tooltipKey: 'publicProfile.sections.statisticsTooltip',
		defaultOn: true
	}
];

export type PublicProfileStatisticsGroup = 'summary' | 'distribution' | 'trends' | 'ratings';

export interface PublicProfileStatisticsDef {
	key: PublicProfileStatisticsKey;
	i18nKey: string;
	group: PublicProfileStatisticsGroup;
	defaultOn: boolean;
}

export const PUBLIC_PROFILE_STATISTICS_GROUPS: {
	group: PublicProfileStatisticsGroup;
	labelKey: string;
}[] = [
	{ group: 'summary', labelKey: 'publicProfile.statGroups.summary' },
	{ group: 'distribution', labelKey: 'statistics.sectionDistributions' },
	{ group: 'trends', labelKey: 'statistics.sectionCharts' },
	{ group: 'ratings', labelKey: 'statistics.ratingStats' }
];

export const PUBLIC_PROFILE_STATISTICS: PublicProfileStatisticsDef[] = [
	{
		key: 'total_books',
		i18nKey: 'statistics.totalBooksAndAuthors',
		group: 'summary',
		defaultOn: true
	},
	{
		key: 'total_authors',
		i18nKey: 'publicProfile.statistics.totalAuthors',
		group: 'summary',
		defaultOn: true
	},
	{
		key: 'avg_books_per_month',
		i18nKey: 'statistics.avgBooksPerMonth',
		group: 'summary',
		defaultOn: false
	},
	{
		key: 'busiest_month',
		i18nKey: 'statistics.busiestMonth',
		group: 'summary',
		defaultOn: false
	},
	{
		key: 'avg_page_count',
		i18nKey: 'statistics.avgPageCount',
		group: 'summary',
		defaultOn: false
	},
	{
		key: 'most_popular_language',
		i18nKey: 'statistics.mostPopularLanguage',
		group: 'summary',
		defaultOn: false
	},
	{
		key: 'language_distribution',
		i18nKey: 'statistics.languageDistribution',
		group: 'distribution',
		defaultOn: false
	},
	{
		key: 'status_distribution',
		i18nKey: 'statistics.statusDistribution',
		group: 'distribution',
		defaultOn: true
	},
	{
		key: 'acquisition_status_distribution',
		i18nKey: 'statistics.acquisitionStatusDistribution',
		group: 'distribution',
		defaultOn: false
	},
	{
		key: 'medium_distribution',
		i18nKey: 'statistics.mediumDistribution',
		group: 'distribution',
		defaultOn: false
	},
	{
		key: 'page_buckets',
		i18nKey: 'statistics.pageBuckets',
		group: 'distribution',
		defaultOn: false
	},
	{
		key: 'pages_read_per_month',
		i18nKey: 'statistics.pagesReadPerMonth',
		group: 'trends',
		defaultOn: false
	},
	{
		key: 'books_finished_per_month',
		i18nKey: 'statistics.booksFinishedPerMonth',
		group: 'trends',
		defaultOn: false
	},
	{
		key: 'books_finished_per_year',
		i18nKey: 'statistics.booksFinishedPerYear',
		group: 'trends',
		defaultOn: false
	},
	{
		key: 'top_authors',
		i18nKey: 'statistics.topAuthors',
		group: 'ratings',
		defaultOn: false
	},
	{
		key: 'books_with_rating',
		i18nKey: 'statistics.booksWithRating',
		group: 'ratings',
		defaultOn: false
	},
	{
		key: 'books_without_rating',
		i18nKey: 'statistics.booksWithoutRating',
		group: 'ratings',
		defaultOn: false
	},
	{
		key: 'average_rating',
		i18nKey: 'statistics.averageRating',
		group: 'ratings',
		defaultOn: false
	},
	{
		key: 'top_rated_books',
		i18nKey: 'statistics.topRated',
		group: 'ratings',
		defaultOn: false
	},
	{
		key: 'worst_rated_books',
		i18nKey: 'statistics.worstRated',
		group: 'ratings',
		defaultOn: false
	}
];

/** Default visibility used when creating a new share link. */
export function defaultPublicProfileVisibilityConfig(): PublicProfileVisibilityConfig {
	return {
		sections: PUBLIC_PROFILE_SECTIONS.filter((s) => s.defaultOn).map((s) => s.key),
		statistics: PUBLIC_PROFILE_STATISTICS.filter((s) => s.defaultOn).map((s) => s.key)
	};
}