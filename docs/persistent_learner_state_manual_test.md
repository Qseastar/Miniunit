# Persistent learner state manual test

1. Start Streamlit in a new private browser window and complete a reviewed diagnostic.
2. Record the sidebar tracked-concept count and mastery, then return to QA.
3. Refresh: the page returns to QA and restores the same state.
4. Keep the URL, restart Streamlit, then reload it: the same profile restores.
5. Click **创建新的本地学习档案**: the new profile is empty. Reopen the old URL to restore the original profile.
6. Click **清空全部学习记录**, then confirm. Refresh and verify the current profile remains empty.

The test is local only: no cross-device sync or login is provided.
