import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import GamificationCard from './GamificationCard.svelte';
import type { GoalProgress } from '$lib/types';

function goal(overrides?: Partial<GoalProgress>): GoalProgress {
	return {
		type: 'pages_per_day',
		target: 20,
		current: 15,
		reached: false,
		...overrides
	};
}

const baseProps = {
	currentStreak: 0,
	longestStreak: 0,
	longestStreakStart: null,
	longestStreakEnd: null,
	goals: [] as GoalProgress[]
};

describe('GamificationCard', () => {
	it('shows the current streak and longest streak', () => {
		render(GamificationCard, {
			props: {
				...baseProps,
				currentStreak: 3,
				longestStreak: 12,
				longestStreakStart: '2026-01-01',
				longestStreakEnd: '2026-01-12'
			}
		});

		expect(screen.getByText('Reading Streaks & Goals')).toBeInTheDocument();
		expect(screen.getByText('Current Streak')).toBeInTheDocument();
		expect(screen.getByText('3')).toBeInTheDocument();
		expect(screen.getByText('Longest Streak')).toBeInTheDocument();
		expect(screen.getByText('12')).toBeInTheDocument();
		expect(screen.getByText('2026-01-01 – 2026-01-12')).toBeInTheDocument();
	});

	it('shows no date range subtitle when there is no longest streak', () => {
		render(GamificationCard, { props: baseProps });
		expect(screen.queryByText(/2026-01-01/)).not.toBeInTheDocument();
	});

	it('renders goal cards with progress when goals are provided', () => {
		render(GamificationCard, {
			props: {
				...baseProps,
				goals: [goal({ current: 15, target: 20, reached: false })]
			}
		});

		expect(screen.getByText('Pages per Day')).toBeInTheDocument();
		expect(screen.getByText('15')).toBeInTheDocument();
		expect(screen.getByText('of 20')).toBeInTheDocument();
		expect(screen.getByText('15 of 20')).toBeInTheDocument();
		expect(screen.queryByText('Goal reached')).not.toBeInTheDocument();
	});

	it('shows a success badge when a goal is reached', () => {
		render(GamificationCard, {
			props: {
				...baseProps,
				goals: [
					goal({ type: 'books_per_month', current: 2, target: 2, reached: true })
				]
			}
		});

		expect(screen.getByText('Books per Month')).toBeInTheDocument();
		expect(screen.getByText('Goal reached')).toBeInTheDocument();
	});

	it('renders multiple goal cards', () => {
		render(GamificationCard, {
			props: {
				...baseProps,
				goals: [
					goal({ current: 15, target: 20 }),
					goal({ type: 'pages_per_month', current: 120, target: 300 }),
					goal({ type: 'books_per_year', current: 25, target: 25, reached: true })
				]
			}
		});

		expect(screen.getByText('Pages per Day')).toBeInTheDocument();
		expect(screen.getByText('Pages per Month')).toBeInTheDocument();
		expect(screen.getByText('Books per Year')).toBeInTheDocument();
		expect(screen.getByText('Goal reached')).toBeInTheDocument();
	});

	it('does not render the goal grid when there are no goals', () => {
		render(GamificationCard, { props: baseProps });
		expect(screen.queryByText('Pages per Day')).not.toBeInTheDocument();
		expect(screen.queryByText('Goal reached')).not.toBeInTheDocument();
	});

	it('shows a loading indicator while loading', () => {
		render(GamificationCard, { props: { ...baseProps, loading: true } });
		expect(document.querySelector('.loading')).toBeInTheDocument();
	});
});