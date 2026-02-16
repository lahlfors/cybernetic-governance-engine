from src.governed_financial_advisor.agents.data_analyst.agent import create_data_analyst_agent

def verify_refactor():
    try:
        agent = create_data_analyst_agent()
        print(f"Agent Name: {agent.name}")
        if agent.tools:
            tool = agent.tools[0]
            print(f"First Tool Type: {type(tool)}")
            print(f"First Tool Dir: {dir(tool)}")
            # Try to find the function name
            if hasattr(tool, 'name'):
                print(f"Tool Name: {tool.name}")
        else:
            print("No tools found!")
        
        # Check if Prompt contains the new tool name
        instruction = agent.instruction
        if "get_market_data_openbb" in instruction:
            print("Instruction verified: Contains 'get_market_data_openbb'")
        else:
            print("Instruction FAILED: Does not contain 'get_market_data_openbb'")
            
    except Exception as e:
        print(f"Verification Failed: {e}")

if __name__ == "__main__":
    verify_refactor()
