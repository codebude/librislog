<script lang="ts">
	import Alert from '$lib/components/Alert.svelte';
	import { api } from '$lib/api';
	import PasswordRequirements from '$lib/components/PasswordRequirements.svelte';
	import { currentUser } from '$lib/stores/auth';
	import { getPasswordChecks, passwordChecksPassed, passwordPattern } from '$lib/password';
	import { isValidEmailFormat } from '$lib/validation';
	import { localizeBackendError } from '$lib/errors';
	import type { User, UserRole } from '$lib/types';
	import { _ } from '$lib/i18n';
	import BackupRestore from '$lib/components/BackupRestore.svelte';

	let users = $state<User[]>([]);
	let firstname = $state('');
	let lastname = $state('');
	let email = $state('');
	let password = $state('');
	let showCreatePassword = $state(false);
	let role = $state<UserRole>('user');

	let editingUserId = $state<number | null>(null);
	let editFirstname = $state('');
	let editLastname = $state('');
	let editEmail = $state('');
	let editPassword = $state('');
	let showEditPassword = $state(false);
	let editRole = $state<UserRole>('user');
	let adminError = $state('');
	let pendingDeleteUserId = $state<number | null>(null);

	let activeTab = $state<'users' | 'backup'>('users');

	const isAdmin = $derived($currentUser?.role === 'admin');

	async function loadUsers() {
		if (!isAdmin) return;
		users = await api.users.list();
	}

	$effect(() => {
		void $currentUser;
		void loadUsers();
	});

	async function createUser() {
		adminError = '';
		if (!firstname.trim() || !lastname.trim() || !email.trim() || !password.trim()) {
			adminError = $_('admin.requiredFieldError');
			return;
		}
		if (!isValidEmailFormat(email)) {
			adminError = $_('auth.invalidEmailError');
			return;
		}
		if (!passwordChecksPassed(getPasswordChecks(password.trim()))) {
			adminError = $_('auth.passwordComplexityError');
			return;
		}
		try {
			await api.users.create({ firstname, lastname, email, password, role });
		} catch (e: unknown) {
			adminError = $_(localizeBackendError(e));
			return;
		}
		firstname = '';
		lastname = '';
		email = '';
		password = '';
		showCreatePassword = false;
		role = 'user';
		await loadUsers();
	}

	function startEdit(user: User) {
		editingUserId = user.id;
		editFirstname = user.firstname;
		editLastname = user.lastname;
		editEmail = user.email;
		editRole = user.role;
		editPassword = '';
		showEditPassword = false;
	}

	function cancelEdit() {
		editingUserId = null;
		editPassword = '';
	}

	async function saveEdit() {
		if (editingUserId === null) return;
		if (!editFirstname.trim() || !editLastname.trim() || !editEmail.trim()) {
			adminError = $_('admin.requiredFieldError');
			return;
		}
		if (!isValidEmailFormat(editEmail)) {
			adminError = $_('auth.invalidEmailError');
			return;
		}
		if ($currentUser?.id === editingUserId && editRole !== 'admin') {
			adminError = $_('admin.cannotChangeOwnRole');
			return;
		}
		if (editPassword.trim() && !passwordChecksPassed(getPasswordChecks(editPassword.trim()))) {
			adminError = $_('auth.passwordComplexityError');
			return;
		}
		adminError = '';
		try {
			await api.users.update(editingUserId, {
				firstname: editFirstname,
				lastname: editLastname,
				email: editEmail,
				role: editRole,
				password: editPassword.trim() ? editPassword : undefined
			});
		} catch (e: unknown) {
			adminError = $_(localizeBackendError(e));
			return;
		}
		editingUserId = null;
		editPassword = '';
		showEditPassword = false;
		await loadUsers();
	}

	function requestDeleteUser(id: number) {
		pendingDeleteUserId = id;
	}

	function cancelDeleteUser() {
		pendingDeleteUserId = null;
	}

	async function confirmDeleteUser() {
		if (pendingDeleteUserId === null) return;
		const id = pendingDeleteUserId;
		pendingDeleteUserId = null;
		try {
			await api.users.delete(id);
			await loadUsers();
			adminError = '';
		} catch (e: unknown) {
			adminError = $_(localizeBackendError(e));
		}
	}
</script>

{#if !isAdmin}
	<div class="max-w-5xl mx-auto">
		<div class="alert alert-error"><span>Admin access required.</span></div>
	</div>
{:else}
	<div class="max-w-5xl mx-auto flex flex-col gap-6">
		<h1 class="text-2xl font-bold">{$_('admin.title')}</h1>

		<div role="tablist" class="tabs tabs-bordered">
			<button role="tab" class="tab" class:tab-active={activeTab === 'users'} onclick={() => activeTab = 'users'}>
				{$_('admin.tabs.users')}
			</button>
			<button role="tab" class="tab" class:tab-active={activeTab === 'backup'} onclick={() => activeTab = 'backup'}>
				{$_('admin.tabs.backup')}
			</button>
		</div>

		{#if activeTab === 'users'}
			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body gap-3">
					<h2 class="text-lg font-semibold">{$_('admin.newUser')}</h2>
					{#if adminError}
						<Alert type="error" onClose={() => (adminError = '')}>
							{adminError}
						</Alert>
					{/if}
					<div class="grid grid-cols-1 md:grid-cols-2 gap-2">
						<label class="form-control">
							<span class="label label-text">{$_('auth.firstname')} *</span>
							<input class="input input-bordered" name="create-firstname" bind:value={firstname} placeholder={$_('auth.firstname')} required />
						</label>
						<label class="form-control">
							<span class="label label-text">{$_('auth.lastname')} *</span>
							<input class="input input-bordered" name="create-lastname" bind:value={lastname} placeholder={$_('auth.lastname')} required />
						</label>
						<label class="form-control">
							<span class="label label-text">{$_('auth.email')} *</span>
							<input type="email" class="input input-bordered" name="create-email" bind:value={email} placeholder={$_('auth.email')} required />
						</label>
						<label class="form-control">
							<span class="label label-text">{$_('auth.password')} *</span>
						<input
							class="input input-bordered validator"
							name="create-password"
							type={showCreatePassword ? 'text' : 'password'}
							bind:value={password}
							placeholder={$_('auth.password')}
							required
							minlength="8"
							pattern={passwordPattern}
							title={$_('password.requirementsTitle')}
						/>
						</label>
						<label class="label cursor-pointer justify-start gap-2 md:col-span-2">
							<input type="checkbox" class="checkbox checkbox-xs" name="create-show-password" bind:checked={showCreatePassword} />
							<span class="label-text text-xs">{$_('common.showPassword')}</span>
						</label>
						<select class="select select-bordered" name="create-role" bind:value={role}>
							<option value="user">user</option>
							<option value="admin">admin</option>
						</select>
					</div>
					<PasswordRequirements {password} />
					<button class="btn btn-primary btn-sm self-start" onclick={createUser}>{$_('admin.create')}</button>
				</div>
			</div>

			<div class="card bg-base-100 border border-base-200 shadow-sm">
				<div class="card-body gap-3">
					<h2 class="text-lg font-semibold">{$_('admin.existingUsers')}</h2>
					<ul class="flex flex-col gap-2">
						{#each users as user}
							<li class="border border-base-200 rounded p-3 flex flex-col gap-2">
								{#if editingUserId === user.id}
									<div class="grid grid-cols-1 md:grid-cols-2 gap-2">
										<label class="form-control">
											<span class="label label-text">{$_('auth.firstname')} *</span>
											<input class="input input-bordered" name="edit-firstname" bind:value={editFirstname} placeholder={$_('auth.firstname')} required />
										</label>
										<label class="form-control">
											<span class="label label-text">{$_('auth.lastname')} *</span>
											<input class="input input-bordered" name="edit-lastname" bind:value={editLastname} placeholder={$_('auth.lastname')} required />
										</label>
									<label class="form-control">
										<span class="label label-text">{$_('auth.email')} *</span>
										<input type="email" class="input input-bordered" name="edit-email" bind:value={editEmail} placeholder={$_('auth.email')} required />
									</label>
										<label class="form-control">
											<span class="label label-text">{$_('user.newPassword')}</span>
										<input
											class="input input-bordered validator"
											name="edit-password"
											type={showEditPassword ? 'text' : 'password'}
											bind:value={editPassword}
											placeholder={$_('user.newPassword')}
											minlength="8"
											pattern={passwordPattern}
											title={$_('password.requirementsTitle')}
										/>
										</label>
										<label class="label cursor-pointer justify-start gap-2 md:col-span-2">
											<input type="checkbox" class="checkbox checkbox-xs" name="edit-show-password" bind:checked={showEditPassword} />
											<span class="label-text text-xs">{$_('common.showPassword')}</span>
										</label>
										<select class="select select-bordered" name="edit-role" bind:value={editRole}>
											<option value="user">user</option>
											<option value="admin">admin</option>
										</select>
									</div>
									<PasswordRequirements password={editPassword} />
									<div class="flex gap-2">
										<button class="btn btn-primary btn-xs" onclick={saveEdit}>{$_('admin.saveChanges')}</button>
										<button class="btn btn-ghost btn-xs" onclick={cancelEdit}>{$_('admin.cancelEdit')}</button>
									</div>
								{:else}
									<div class="flex items-center justify-between gap-2">
										<div>
											<p class="font-semibold">{user.firstname} {user.lastname}</p>
											<p class="text-sm text-base-content/70">{user.email} - {user.role}</p>
											{#if $currentUser?.id === user.id}
												<p class="text-xs text-base-content/60 mt-1">{$_('admin.selfDeleteHint')}</p>
											{/if}
										</div>
										<div class="flex gap-2">
											<button class="btn btn-outline btn-xs" onclick={() => startEdit(user)}>{$_('admin.edit')}</button>
											{#if $currentUser?.id !== user.id}
											<button class="btn btn-error btn-outline btn-xs" onclick={() => requestDeleteUser(user.id)}>{$_('common.delete')}</button>
										{/if}
									</div>
								</div>
								{/if}
							</li>
						{/each}
					</ul>
				</div>
			</div>
		{:else if activeTab === 'backup'}
			<BackupRestore />
		{/if}
	</div>
{/if}

<dialog class="modal" class:modal-open={pendingDeleteUserId !== null}>
	<div class="modal-box">
		<h3 class="text-lg font-bold">{$_('admin.deleteConfirmTitle')}</h3>
		<p class="py-3 text-sm text-base-content/70">{$_('admin.deleteConfirmBody')}</p>
		<div class="modal-action">
			<button type="button" class="btn btn-ghost" onclick={cancelDeleteUser}>{$_('common.cancel')}</button>
			<button type="button" class="btn btn-error" onclick={confirmDeleteUser}>{$_('common.delete')}</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button type="button" onclick={cancelDeleteUser}>{$_('common.close')}</button>
	</form>
</dialog>
