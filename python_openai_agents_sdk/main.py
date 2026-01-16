from agents import (Agent, Runner, AgentHooks, Tool, RunContextWrapper,
                    TResponseInputItem,)
from functools import partial
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools
from typing import Any
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage,
                               auth_tool)

import globals


class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self,
                       context: RunContextWrapper,
                       agent: Agent) -> None:
        self.event_counter += 1
        print(f"### ({self.display_name}) {
              self.event_counter}: Agent {agent.name} started")

    async def on_end(self,
                     context: RunContextWrapper,
                     agent: Agent,
                     output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended with output {output}"
                agent.name} ended"
        )

    async def on_handoff(self,
                         context: RunContextWrapper,
                         agent: Agent,
                         source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self,
                            context: RunContextWrapper,
                            agent: Agent,
                            tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}:"
            f" Agent {agent.name} started tool {tool.name}"
            f" with context: {context.context}"
        )

    async def on_tool_end(self,
                          context: RunContextWrapper,
                          agent: Agent,
                          tool: Tool,
                          result: str) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended tool {tool.name} with result {result}"
                agent.name} ended tool {tool.name}"
        )


async def main():

    context = {
        "user_id": os.getenv("ARCADE_USER_ID"),
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client, tools=['PagerdutyApi_ListExistingIncidents', 'PagerdutyApi_GetIncidentDetails', 'PagerdutyApi_ListIncidentLogEntries', 'PagerdutyApi_ListIncidentAlerts', 'PagerdutyApi_ListIncidentNotes', 'PagerdutyApi_AddIncidentNote', 'PagerdutyApi_UpdateIncidentStatus', 'PagerdutyApi_GetServiceDetails', 'PagerdutyApi_ListServices', 'DatadogApi_ListLogs', 'DatadogApi_ListLogsMatchingQuery', 'DatadogApi_SearchDatadogEvents', 'DatadogApi_GetEventDetails', 'DatadogApi_SearchDatadogIncidents', 'DatadogApi_GetIncidentDetails', 'DatadogApi_SearchDatadogIssues', 'DatadogApi_GetErrorTrackingIssueDetails', 'DatadogApi_SearchRumEvents', 'DatadogApi_ListRumEvents', 'DatadogApi_QueryTimeseriesData', 'DatadogApi_QueryScalarData'], toolkits=["Slack", "Gmail", "GoogleCalendar"]
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name="",
        instructions="You are a Debug Investigation Agent that helps investigate and resolve incidents. When triggered with an incident, follow this workflow:

1. **Retrieve Incident Details**: Use PagerDuty tools to get full incident context, affected services, and existing notes.

2. **Gather Log Data**: Query Datadog logs around the incident timeframe. Search for errors, exceptions, and anomalies. Use RUM events for user impact analysis.

3. **Correlate Issues**: Search for related Datadog incidents, error tracking issues, and events that might explain the root cause.

4. **Analyze Metrics**: Query relevant time series and scalar metrics to understand system behavior during the incident.

5. **Communicate Findings**: Post incident analysis updates to Slack to keep stakeholders informed.

6. **Document Root Cause**: Once investigation is complete, send a root cause analysis summary via Gmail to relevant parties.

7. **Schedule Review**: Create a Google Calendar event for a post-incident review meeting with the team.

Always add investigation notes to the PagerDuty incident and update its status as the investigation progresses.",
        model=os.environ["OPENAI_MODEL"],
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name="")
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())