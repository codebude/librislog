<script lang="ts">
	import { BookOpen, CalendarDays, CalendarRange, Flame, Library, Trophy } from '@lucide/svelte';
	import type { GoalProgress, GoalType } from '$lib/types';
	import { _ } from '$lib/i18n';

	interface Props {
		currentStreak: number;
		longestStreak: number;
		longestStreakStart: string | null;
		longestStreakEnd: string | null;
		goals: GoalProgress[];
		loading?: boolean;
	}

	let {
		currentStreak,
		longestStreak,
		longestStreakStart,
		longestStreakEnd,
		goals,
		loading = false
	}: Props = $props();

	const GOAL_LABEL_KEYS: Record<GoalType, string> = {
		pages_per_day: 'dashboard.goalPagesPerDay',
		pages_per_month: 'dashboard.goalPagesPerMonth',
		books_per_month: 'dashboard.goalBooksPerMonth',
		books_per_year: 'dashboard.goalBooksPerYear'
	};

	const GOAL_BAR_CLASSES: Record<GoalType, string> = {
		pages_per_day: 'progress-primary',
		pages_per_month: 'progress-info',
		books_per_month: 'progress-warning',
		books_per_year: 'progress-success'
	};

	const GOAL_VALUE_COLORS: Record<GoalType, string> = {
		pages_per_day: 'text-primary',
		pages_per_month: 'text-info',
		books_per_month: 'text-warning',
		books_per_year: 'text-success'
	};

	function goalIcon(type: GoalType) {
		switch (type) {
			case 'pages_per_day':
				return BookOpen;
			case 'pages_per_month':
				return CalendarDays;
			case 'books_per_month':
				return Library;
			case 'books_per_year':
				return CalendarRange;
			default:
				return BookOpen;
		}
	}

	function dateRangeLabel(start: string | null, end: string | null): string {
		if (!start || !end) return '';
		return $_('dashboard.longestStreakDateRange', { values: { start, end } });
	}
</script>

<div class="card bg-base-100 border border-base-200 shadow-sm">
	<div class="card-body gap-4">
		<h2 class="card-title">
			<span class="inline-flex items-center gap-2">
				<span class="text-warning"><Trophy class="w-5 h-5" /></span>
				{$_('dashboard.gamificationTitle')}
			</span>
		</h2>

		{#if loading}
			<div class="py-6 text-center"><span class="loading loading-spinner loading-md"></span></div>
		{:else}
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
				<div class="stat bg-base-200/40 rounded-xl border border-base-200">
					<div class="stat-figure text-warning">
						<Flame class="w-8 h-8" />
					</div>
					<div class="stat-title">{$_('dashboard.currentStreak')}</div>
					<div class="stat-value text-warning">{currentStreak}</div>
					<div class="stat-desc">{$_('dashboard.currentStreakHint')}</div>
				</div>

				<div class="stat bg-base-200/40 rounded-xl border border-base-200">
					<div class="stat-figure text-success">
						<Trophy class="w-8 h-8" />
					</div>
					<div class="stat-title">{$_('dashboard.longestStreak')}</div>
					<div class="stat-value text-success">{longestStreak}</div>
					<div class="stat-desc">{dateRangeLabel(longestStreakStart, longestStreakEnd)}</div>
				</div>
			</div>

			{#if goals.length > 0}
				<div class="divider my-1"></div>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
					{#each goals as goal (goal.type)}
						{@const Icon = goalIcon(goal.type)}
						<div class="bg-base-200/40 rounded-xl border border-base-200 p-4 flex flex-col gap-2">
							<div class="flex items-center justify-between gap-2">
								<span class="inline-flex items-center gap-2 text-sm font-medium">
									<Icon class="w-4 h-4 {GOAL_VALUE_COLORS[goal.type]}" />
									{$_(GOAL_LABEL_KEYS[goal.type])}
								</span>
								{#if goal.reached}
									<span class="badge badge-success badge-sm gap-1">
										<Trophy class="w-3 h-3" />
										{$_('dashboard.goalReached')}
									</span>
								{/if}
							</div>
							<div class="flex items-baseline justify-between gap-2">
								<span class="text-lg font-bold {GOAL_VALUE_COLORS[goal.type]}">{goal.current}</span>
								<span class="text-sm text-base-content/60">{$_('dashboard.goalOf', { values: { target: goal.target } })}</span>
							</div>
							<progress
								class="progress w-full {GOAL_BAR_CLASSES[goal.type]}"
								value={goal.reached ? goal.target : Math.min(goal.current, goal.target)}
								max={goal.target}
								aria-label={$_('dashboard.goalProgress', { values: { current: goal.current, target: goal.target } })}
							></progress>
							<div class="text-xs text-base-content/50">
								{$_('dashboard.goalProgress', { values: { current: goal.current, target: goal.target } })}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		{/if}
	</div>
</div>