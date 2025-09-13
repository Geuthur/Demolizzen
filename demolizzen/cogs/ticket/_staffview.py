# Discord
import discord


class RoleSelectView(discord.ui.View):
    def __init__(self, guild: discord.Guild, timeout=60):
        super().__init__(timeout=timeout)
        self.guild = guild
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in self.guild.roles
            if not role.is_default()
        ]
        self.select = discord.ui.Select(
            placeholder="Select staff roles...",
            min_values=1,
            max_values=min(25, len(options)),
            options=options,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)
        self.selected_roles = None

    async def select_callback(self, interaction: discord.Interaction):
        selected_ids = self.select.values
        self.selected_roles = [
            discord.utils.get(self.guild.roles, id=int(role_id))
            for role_id in selected_ids
            if discord.utils.get(self.guild.roles, id=int(role_id)) is not None
        ]
        await interaction.response.defer()
        self.stop()
