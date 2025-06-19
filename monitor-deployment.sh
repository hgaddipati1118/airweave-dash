#!/bin/bash

# Monitor Infrastructure Deployment
STACK_NAME="prod-airweave-infrastructure-stack"
REGION="us-east-1"

echo "🔄 Monitoring $STACK_NAME deployment..."
echo "Started at: $(date)"
echo "Expected completion: $(date -d '+20 minutes' 2>/dev/null || date -v +20M)"
echo ""

check_count=0
while true; do
    check_count=$((check_count + 1))
    current_time=$(date "+%H:%M:%S")
    
    echo "[$current_time] Check #$check_count - Getting stack status..."
    
    # Check if stack exists and get status
    if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION > /tmp/stack_status.txt 2>&1; then
        # Extract stack status
        echo "✅ Stack found - checking detailed status..."
        
        # Get the latest events (last 5)
        echo "📋 Recent events:"
        aws cloudformation describe-stack-events \
            --stack-name $STACK_NAME \
            --region $REGION \
            --max-items 5 > /tmp/events.txt 2>&1
            
        if [ $? -eq 0 ]; then
            echo "   Events captured - check /tmp/events.txt for details"
        else
            echo "   Unable to get events (might be due to shell config)"
        fi
        
        # Check for completion keywords in the output
        if grep -q "CREATE_COMPLETE\|UPDATE_COMPLETE" /tmp/stack_status.txt; then
            echo ""
            echo "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!"
            echo "Finished at: $(date)"
            break
        elif grep -q "FAILED\|ROLLBACK" /tmp/stack_status.txt; then
            echo ""
            echo "❌ DEPLOYMENT FAILED!"
            echo "Check AWS Console or run:"
            echo "aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $REGION"
            break
        else
            echo "   Still in progress..."
        fi
    else
        echo "⏳ Stack not yet visible or still being created..."
    fi
    
    echo ""
    echo "⏰ Waiting 30 seconds for next check..."
    sleep 30
done

echo ""
echo "🏁 Monitoring completed at: $(date)" 